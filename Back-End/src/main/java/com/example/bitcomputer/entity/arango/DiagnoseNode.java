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
@Document("Diagnose")
public class DiagnoseNode {

    @Id
    private String id;

    private String code;
    private String name;
    private int dose;
    private int time;
    private int days;
}
