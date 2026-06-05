package com.example.bitcomputer.model;

import lombok.Data;

@Data
@Deprecated
public class RadiologyReportResponseDTO {
    int radiologyRequestId;
    int patientId;
    int employeeId;
    int deptId;
    boolean result; // true => 의심, false => 이상 없음
    String summary;
    String imageUrl; // overlay 이미지 경로
    String status;
}

