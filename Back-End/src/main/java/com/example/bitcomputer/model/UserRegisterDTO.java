package com.example.bitcomputer.model;

import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class UserRegisterDTO {
    String name;
    int deptId;
    String role;
    String username;
    String password;
}
