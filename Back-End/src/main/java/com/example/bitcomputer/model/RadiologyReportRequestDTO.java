package com.example.bitcomputer.model;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.util.Date;

@Data
public class RadiologyReportRequestDTO {
    int radiologyRequestId;
    int patientId;
    int employeeId;
    int deptId;
    String symptomDetail;
    String memo;
    
    @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd")
    Date entryDate;
    
    String detailImageAddress;
    String view;
}

