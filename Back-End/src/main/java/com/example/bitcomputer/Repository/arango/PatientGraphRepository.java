package com.example.bitcomputer.Repository.arango;

import com.example.bitcomputer.entity.arango.PatientNode;
import com.arangodb.springframework.repository.ArangoRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public interface PatientGraphRepository extends ArangoRepository<PatientNode, String> {

    Optional<PatientNode> findByIdentityNumber(String identityNumber);
}
