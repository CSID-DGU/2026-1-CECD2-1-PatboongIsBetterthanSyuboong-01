package com.example.bitcomputer.Repository.arango;

import com.example.bitcomputer.entity.arango.DiseaseNode;
import com.arangodb.springframework.repository.ArangoRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public interface DiseaseGraphRepository extends ArangoRepository<DiseaseNode, String> {

    Optional<DiseaseNode> findByCode(String code);
}
