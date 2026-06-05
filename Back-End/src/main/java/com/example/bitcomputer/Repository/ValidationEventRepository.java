package com.example.bitcomputer.Repository;

import com.example.bitcomputer.entity.ValidationEvent;
import com.example.bitcomputer.entity.ValidationEventStatus;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface ValidationEventRepository extends JpaRepository<ValidationEvent, Long> {
    List<ValidationEvent> findTop20ByStatusOrderByCreatedAtAsc(ValidationEventStatus status);
}
