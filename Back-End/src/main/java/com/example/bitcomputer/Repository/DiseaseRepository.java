package com.example.bitcomputer.Repository;

import com.example.bitcomputer.entity.Disease;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Optional;

public interface DiseaseRepository extends JpaRepository<Disease, Integer> {
    Optional<Disease> findByCode(String code);
    Optional<Disease> findByName(String name);

    @Query("""
            SELECT d FROM Disease d WHERE
            LOWER(d.code) LIKE LOWER(CONCAT('%', :codePart, '%'))
            OR LOWER(d.name) LIKE LOWER(CONCAT('%', :namePart, '%'))
            OR (d.nameEn IS NOT NULL AND LOWER(d.nameEn) LIKE LOWER(CONCAT('%', :codePart, '%')))
            OR (d.nameEn IS NOT NULL AND LOWER(d.nameEn) LIKE LOWER(CONCAT('%', :namePart, '%')))
            """)
    Page<Disease> searchByCodeOrNameOrNameEn(
            @Param("codePart") String codePart,
            @Param("namePart") String namePart,
            Pageable pageable
    );
}