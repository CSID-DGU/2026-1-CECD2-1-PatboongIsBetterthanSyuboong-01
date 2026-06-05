package com.example.bitcomputer.controller;

import com.example.bitcomputer.Repository.PhraseRepository;
import com.example.bitcomputer.entity.Phrase;
import com.example.bitcomputer.model.PhraseDTO;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.List;
import java.util.stream.Collectors;

@Slf4j
@RestController
@RequestMapping("/api/agent/phrase")
public class PhraseController {

    private final PhraseRepository phraseRepository;

    public PhraseController(PhraseRepository phraseRepository) {
        this.phraseRepository = phraseRepository;
    }

    /**
     * 상용구 목록 조회
     * GET /api/agent/phrase?employeeId=1
     */
    @GetMapping
    public ResponseEntity<List<PhraseDTO>> getPhrases(
            @RequestParam("employeeId") Integer employeeId) {
        List<PhraseDTO> result = phraseRepository
                .findByEmployeeIdOrderByCreatedAtDesc(employeeId)
                .stream()
                .map(this::toDTO)
                .collect(Collectors.toList());
        return ResponseEntity.ok(result);
    }

    /**
     * 상용구 생성
     * POST /api/agent/phrase
     * Body: { employeeId, title, content }
     */
    @PostMapping
    public ResponseEntity<PhraseDTO> createPhrase(
            @RequestBody PhraseDTO request) {
        if (request.getEmployeeId() == null || request.getTitle() == null || request.getContent() == null) {
            return ResponseEntity.badRequest().build();
        }
        Phrase entity = new Phrase();
        entity.setEmployeeId(request.getEmployeeId());
        entity.setTitle(request.getTitle());
        entity.setContent(request.getContent());
        entity.setCreatedAt(LocalDateTime.now());
        entity.setUpdatedAt(LocalDateTime.now());

        Phrase saved = phraseRepository.save(entity);
        return ResponseEntity.status(HttpStatus.CREATED).body(toDTO(saved));
    }

    /**
     * 상용구 수정
     * PUT /api/agent/phrase/{id}
     * Body: { title, content }
     */
    @PutMapping("/{id}")
    public ResponseEntity<PhraseDTO> updatePhrase(
            @PathVariable Integer id,
            @RequestBody PhraseDTO request) {
        return phraseRepository.findById(id)
                .map(entity -> {
                    if (request.getTitle() != null)   entity.setTitle(request.getTitle());
                    if (request.getContent() != null) entity.setContent(request.getContent());
                    entity.setUpdatedAt(LocalDateTime.now());
                    return ResponseEntity.ok(toDTO(phraseRepository.save(entity)));
                })
                .orElse(ResponseEntity.notFound().build());
    }

    /**
     * 상용구 삭제
     * DELETE /api/agent/phrase/{id}
     */
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deletePhrase(@PathVariable Integer id) {
        if (!phraseRepository.existsById(id)) {
            return ResponseEntity.notFound().build();
        }
        phraseRepository.deleteById(id);
        return ResponseEntity.noContent().build();
    }

    private PhraseDTO toDTO(Phrase entity) {
        PhraseDTO dto = new PhraseDTO();
        dto.setId(entity.getId());
        dto.setEmployeeId(entity.getEmployeeId());
        dto.setTitle(entity.getTitle());
        dto.setContent(entity.getContent());
        return dto;
    }
}
