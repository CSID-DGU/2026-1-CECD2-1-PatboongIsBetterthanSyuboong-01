package com.example.bitcomputer.model;


import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.util.Date;

@Data
public class WriteHistoryDTO {
    int employeeId;
    int patientId;
    int deptId;
    String symptomDetail;
    String memo;

    @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd")
    Date entryDate;
}
