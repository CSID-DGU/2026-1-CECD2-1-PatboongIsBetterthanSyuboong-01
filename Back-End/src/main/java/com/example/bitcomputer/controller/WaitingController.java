package com.example.bitcomputer.controller;
import org.springframework.web.bind.annotation.*;

import com.example.bitcomputer.jwt.TokenInfo;
import com.example.bitcomputer.model.WaitingDTO;
import com.example.bitcomputer.service.WaitingService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;

import java.util.List;

@RestController
@RequestMapping("/api/waiting")
public class WaitingController {

    private final WaitingService waitingService;

    public WaitingController(WaitingService waitingService) {
        this.waitingService = waitingService;
    }

    @PostMapping("/register")
    public ResponseEntity<TokenInfo> registerWaiting(@RequestBody WaitingDTO waitingDTO) {
        try {
            // 필수 필드 검증
            if (waitingDTO.getPatientId() <= 0) {
                return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(null);
            }

            // 접수 등록
            TokenInfo tokenInfo = waitingService.registerWaiting(waitingDTO);

            if (tokenInfo != null) {
                return ResponseEntity.ok(tokenInfo);
            } else {
                return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(null);
            }

        } catch (IllegalArgumentException e) {
            return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(null);
        } catch (Exception e) {
            return  ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(null);
        }
    }

    @GetMapping("/get_list")
    public ResponseEntity<List<WaitingDTO>> getWaitingList() {
        try {
            List<WaitingDTO> waitingList = waitingService.getWaitingList();

            if (waitingList != null && !waitingList.isEmpty()) {
                return ResponseEntity.ok(waitingList);
            } else {
                // 빈 목록도 정상 응답으로 처리
                return ResponseEntity.ok(waitingList);
            }

        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(null);
        }
    }

    @PutMapping("{patientid}/complete")
    public ResponseEntity<TokenInfo> updateWaitingState(@PathVariable("patientid") int patientid) {
        try {
            // 필수 필드 검증
            if (patientid <= 0) {
                return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(null);
            }

            // 대기 상태 변경
            TokenInfo tokenInfo = waitingService.updateWaitingState(patientid);

            if (tokenInfo != null) {
                return ResponseEntity.ok(tokenInfo);
            } else {
                return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(null);
            }

        } catch (IllegalArgumentException e) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(null);
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(null);
        }
    }

    @PutMapping("entry/{waitingId}/complete")
    public ResponseEntity<TokenInfo> updateWaitingEntryState(@PathVariable("waitingId") int waitingId) {
        try {
            if (waitingId <= 0) {
                return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(null);
            }
            TokenInfo tokenInfo = waitingService.updateWaitingStateByWaitingId(waitingId);
            return ResponseEntity.ok(tokenInfo);
        } catch (IllegalArgumentException e) {
            return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(null);
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(null);
        }
    }

    @PutMapping("{patientid}/hold")
    public ResponseEntity<TokenInfo> updateWaitingStateToHold(@PathVariable("patientid") int patientid) {
        try {
            // 필수 필드 검증
            if (patientid <= 0) {
                return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(null);
            }

            // 대기 상태를 보류로 변경
            TokenInfo tokenInfo = waitingService.updateWaitingStateToHold(patientid);

            if (tokenInfo != null) {
                return ResponseEntity.ok(tokenInfo);
            } else {
                return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(null);
            }

        } catch (IllegalArgumentException e) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(null);
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(null);
        }
    }

    @PutMapping("entry/{waitingId}/hold")
    public ResponseEntity<TokenInfo> updateWaitingEntryStateToHold(@PathVariable("waitingId") int waitingId) {
        try {
            if (waitingId <= 0) {
                return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(null);
            }
            TokenInfo tokenInfo = waitingService.updateWaitingStateToHoldByWaitingId(waitingId);
            return ResponseEntity.ok(tokenInfo);
        } catch (IllegalArgumentException e) {
            return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(null);
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(null);
        }
    }

    @DeleteMapping("entry/{waitingId}")
    public ResponseEntity<Void> deleteWaitingEntry(@PathVariable("waitingId") int waitingId) {
        try {
            if (waitingId <= 0) {
                return ResponseEntity.badRequest().build();
            }
            waitingService.deleteWaitingByWaitingId(waitingId);
            return ResponseEntity.noContent().build();
        } catch (IllegalArgumentException e) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).build();
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).build();
        }
    }
}
