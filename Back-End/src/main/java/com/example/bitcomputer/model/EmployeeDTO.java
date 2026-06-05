package com.example.bitcomputer.model;

import lombok.Data;

@Data
public class EmployeeDTO {
    int id;
    String name;
    int deptId;
    String role;
    String username;
    String password;
}
