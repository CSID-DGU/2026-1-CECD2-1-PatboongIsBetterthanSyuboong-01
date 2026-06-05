package com.example.bitcomputer.model;

import lombok.Data;

@Data
public class HistoryDiseaseDTO {
    int id;
    int historyId;
    String degree;
    String code;    //질병 코드
    String name;
}
