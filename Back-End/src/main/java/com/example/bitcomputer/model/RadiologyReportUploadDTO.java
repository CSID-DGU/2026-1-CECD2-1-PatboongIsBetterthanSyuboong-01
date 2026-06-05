package com.example.bitcomputer.model;

import lombok.Data;

@Data
public class RadiologyReportUploadDTO {
    int patientId;
    int employeeId;
    int deptId;
    String symptomDetail;
    String memo;
    String entryDate; // "yyyy-MM-dd" 형식
}

