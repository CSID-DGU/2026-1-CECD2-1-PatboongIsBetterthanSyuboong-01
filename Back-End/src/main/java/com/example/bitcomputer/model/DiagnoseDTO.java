package com.example.bitcomputer.model;

import lombok.Data;

@Data
public class DiagnoseDTO {
    int id;
    String code;
    String name;
    int dose;
    int time;
    int days;
}
