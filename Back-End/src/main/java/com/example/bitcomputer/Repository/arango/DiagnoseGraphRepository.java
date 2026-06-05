package com.example.bitcomputer.Repository.arango;

import com.example.bitcomputer.entity.arango.DiagnoseNode;
import com.arangodb.springframework.repository.ArangoRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public interface DiagnoseGraphRepository extends ArangoRepository<DiagnoseNode, String> {

    Optional<DiagnoseNode> findByCode(String code);
}
