package com.example.bitcomputer.entity.arango;

import com.arangodb.springframework.annotation.Document;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.Id;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Document("Patient")
public class PatientNode {

    @Id
    private String id;

    private String name;
    private String identityNumber;
    private String gender;
    private int age;
}
