package com.example.bitcomputer.model;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.util.Date;

@Data
public class HistoryDTO {
    Integer id;
    Integer employeeId;
    Integer patientId;
    Integer deptId;
    String symptomDetail;
    String memo;
    Date startDate;
    Date endDate;

    @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd")
    Date entryDate;
}
