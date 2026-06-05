package com.example.bitcomputer.model;

import lombok.Data;

import java.util.List;

@Data
public class PastPrescriptionDTO {

    private Integer historyId;
    private String entryDate;   // yyyy-MM-dd
    private List<DiagnoseInfo> diagnoses;

    @Data
    public static class DiagnoseInfo {
        private String code;
        private String name;
        private Integer dose;
        private Integer time;
        private Integer days;
    }
}
