package com.example.bitcomputer.serviceImpl;

import com.example.bitcomputer.Repository.DeptRepository;
import com.example.bitcomputer.Repository.WaitingRepository;
import com.example.bitcomputer.entity.Waiting;
import com.example.bitcomputer.jwt.JwtTokenProvider;
import com.example.bitcomputer.jwt.TokenInfo;
import com.example.bitcomputer.model.WaitingDTO;
import com.example.bitcomputer.service.WaitingService;
import jakarta.transaction.Transactional;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.time.LocalDate;
import java.time.LocalTime;
import java.util.List;
import java.util.Optional;
import java.util.stream.Collectors;

@Service
public class WaitingServiceImpl implements WaitingService {
    private final WaitingRepository waitingRepository;
    private final DeptRepository deptRepository;
    private final JwtTokenProvider jwtTokenProvider;

    public WaitingServiceImpl(WaitingRepository waitingRepository,
                              DeptRepository deptRepository,
                              JwtTokenProvider jwtTokenProvider) {
        this.waitingRepository = waitingRepository;
        this.deptRepository = deptRepository;
        this.jwtTokenProvider = jwtTokenProvider;
    }

    @Override
    @Transactional
    public TokenInfo registerWaiting(WaitingDTO waitingDTO) {
        Waiting waiting = new Waiting();
        waiting.setPatientId(waitingDTO.getPatientId());
        waiting.setDeptId(resolveDeptId(waitingDTO.getDeptId()));
        waiting.setSymptom(waitingDTO.getSymptom());
        waiting.setDepartment(waitingDTO.getDepartment());
        waiting.setDoctor(waitingDTO.getDoctor());
        waiting.setVisitTime(waitingDTO.getVisitTime());
        waiting.setVisitType(waitingDTO.getVisitType());
        waiting.setVisitReason(waitingDTO.getVisitReason());
        waiting.setVisitRoute(waitingDTO.getVisitRoute());
        waiting.setTreatmentType(waitingDTO.getTreatmentType());
        waiting.setMemo(waitingDTO.getMemo());
        waiting.setEntryDate(resolveEntryDate(waitingDTO));
        waiting.setState(waitingDTO.getState() != null ? waitingDTO.getState() : "waiting");

        // 저장
        Waiting savedWaiting = waitingRepository.save(waiting);

        // JWT 토큰 생성
        String patientIdStr = String.valueOf(savedWaiting.getPatientId());
        String accessToken = jwtTokenProvider.generateAccessToken(patientIdStr);
        String refreshToken = jwtTokenProvider.generateRefreshToken(patientIdStr);

        return new TokenInfo("Bearer", accessToken, refreshToken);
    }

    @Override
    public List<WaitingDTO> getWaitingList() {
        List<Waiting> waitingList = waitingRepository.findAll();

        return waitingList.stream()
                .map(this::convertToDTO)
                .collect(Collectors.toList());
    }

    @Override
    @Transactional
    public TokenInfo updateWaitingState(int patientId) {
        // 상태에 관계없이 최신 대기 정보를 찾음 (completed가 아닌 경우)
        Optional<Waiting> optionalWaiting = waitingRepository.findFirstByPatientIdOrderByIdDesc(patientId);

        if (optionalWaiting.isEmpty()) {
            throw new IllegalArgumentException("해당 환자의 대기 정보를 찾을 수 없습니다.");
        }

        Waiting waiting = optionalWaiting.get();

        // 이미 완료된 경우는 변경하지 않음
        if ("completed".equals(waiting.getState())) {
            throw new IllegalArgumentException("이미 완료된 진료입니다.");
        }

        waiting.setState("completed");

        Waiting updatedWaiting = waitingRepository.save(waiting);

        // JWT 토큰 생성
        String patientIdStr = String.valueOf(updatedWaiting.getPatientId());
        String accessToken = jwtTokenProvider.generateAccessToken(patientIdStr);
        String refreshToken = jwtTokenProvider.generateRefreshToken(patientIdStr);

        return new TokenInfo("Bearer", accessToken, refreshToken);

    }

    @Override
    @Transactional
    public TokenInfo updateWaitingStateToHold(int patientId) {
        // 상태에 관계없이 최신 대기 정보를 찾음 (completed가 아닌 경우)
        Optional<Waiting> optionalWaiting = waitingRepository.findFirstByPatientIdOrderByIdDesc(patientId);

        if (optionalWaiting.isEmpty()) {
            throw new IllegalArgumentException("해당 환자의 대기 정보를 찾을 수 없습니다.");
        }

        Waiting waiting = optionalWaiting.get();

        // 이미 완료된 경우는 변경하지 않음
        if ("completed".equals(waiting.getState())) {
            throw new IllegalArgumentException("이미 완료된 진료는 보류로 변경할 수 없습니다.");
        }

        waiting.setState("hold");

        Waiting updatedWaiting = waitingRepository.save(waiting);

        // JWT 토큰 생성
        String patientIdStr = String.valueOf(updatedWaiting.getPatientId());
        String accessToken = jwtTokenProvider.generateAccessToken(patientIdStr);
        String refreshToken = jwtTokenProvider.generateRefreshToken(patientIdStr);

        return new TokenInfo("Bearer", accessToken, refreshToken);
    }

    @Override
    @Transactional
    public TokenInfo updateWaitingStateByWaitingId(int waitingId) {
        Waiting waiting = waitingRepository.findById(waitingId)
                .orElseThrow(() -> new IllegalArgumentException("해당 대기 정보를 찾을 수 없습니다."));

        if ("completed".equals(waiting.getState())) {
            throw new IllegalArgumentException("이미 완료된 진료입니다.");
        }

        waiting.setState("completed");
        Waiting updatedWaiting = waitingRepository.save(waiting);

        String patientIdStr = String.valueOf(updatedWaiting.getPatientId());
        String accessToken = jwtTokenProvider.generateAccessToken(patientIdStr);
        String refreshToken = jwtTokenProvider.generateRefreshToken(patientIdStr);
        return new TokenInfo("Bearer", accessToken, refreshToken);
    }

    @Override
    @Transactional
    public TokenInfo updateWaitingStateToHoldByWaitingId(int waitingId) {
        Waiting waiting = waitingRepository.findById(waitingId)
                .orElseThrow(() -> new IllegalArgumentException("해당 대기 정보를 찾을 수 없습니다."));

        if ("completed".equals(waiting.getState())) {
            throw new IllegalArgumentException("이미 완료된 진료는 보류로 변경할 수 없습니다.");
        }

        waiting.setState("hold");
        Waiting updatedWaiting = waitingRepository.save(waiting);

        String patientIdStr = String.valueOf(updatedWaiting.getPatientId());
        String accessToken = jwtTokenProvider.generateAccessToken(patientIdStr);
        String refreshToken = jwtTokenProvider.generateRefreshToken(patientIdStr);
        return new TokenInfo("Bearer", accessToken, refreshToken);
    }

    @Override
    @Transactional
    public void deleteWaitingByWaitingId(int waitingId) {
        Waiting waiting = waitingRepository.findById(waitingId)
                .orElseThrow(() -> new IllegalArgumentException("해당 대기 정보를 찾을 수 없습니다."));
        waitingRepository.delete(waiting);
    }

    private WaitingDTO convertToDTO(Waiting waiting) {
        WaitingDTO dto = new WaitingDTO();
        dto.setId(waiting.getId());
        dto.setPatientId(waiting.getPatientId());
        dto.setDeptId(waiting.getDeptId());
        dto.setSymptom(waiting.getSymptom());
        dto.setDepartment(waiting.getDepartment());
        dto.setDoctor(waiting.getDoctor());
        dto.setVisitTime(waiting.getVisitTime());
        dto.setVisitType(waiting.getVisitType());
        dto.setVisitReason(waiting.getVisitReason());
        dto.setVisitRoute(waiting.getVisitRoute());
        dto.setTreatmentType(waiting.getTreatmentType());
        dto.setMemo(waiting.getMemo());
        dto.setEntryDate(waiting.getEntryDate());
        dto.setState(waiting.getState());
        return dto;
    }

    private LocalDateTime resolveEntryDate(WaitingDTO waitingDTO) {
        LocalDate date = waitingDTO.getEntryDate() != null
                ? waitingDTO.getEntryDate().toLocalDate()
                : LocalDate.now();
        LocalTime time = LocalTime.now();
        if (waitingDTO.getVisitTime() != null && !waitingDTO.getVisitTime().isBlank()) {
            try {
                time = LocalTime.parse(waitingDTO.getVisitTime());
            } catch (Exception ignored) {
                // 잘못된 접수시간은 현재 시간으로 저장한다.
            }
        }
        return LocalDateTime.of(date, time);
    }

    private int resolveDeptId(int requestedDeptId) {
        int deptId = requestedDeptId > 0 ? requestedDeptId : 1;
        if (deptRepository.existsById(deptId)) {
            return deptId;
        }
        return deptRepository.existsById(1) ? 1 : deptId;
    }


}
