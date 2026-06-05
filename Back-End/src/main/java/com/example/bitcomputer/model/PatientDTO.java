package com.example.bitcomputer.model;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.util.Date;

@Data
public class PatientDTO {
    int id;
    String name;
    String phoneNumber;
    String identityNumber;
    String visitNumber;

    @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd")
    Date birth;
    String gender;
}
