package com.example.bitcomputer.model;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.Date;

@Data
public class WaitingDTO {
    int id;
    int patientId;
    int deptId;
    String symptom;
    String department;
    String doctor;
    String visitTime;
    String visitType;
    String visitReason;
    String visitRoute;
    String treatmentType;
    String memo;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    LocalDateTime entryDate;
    String state;
}
