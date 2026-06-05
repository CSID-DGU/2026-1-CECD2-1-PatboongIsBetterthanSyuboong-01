package com.example.bitcomputer.service;

import com.example.bitcomputer.model.UserRegisterDTO;
import com.example.bitcomputer.model.LoginRequestDTO;
import com.example.bitcomputer.jwt.TokenInfo;

public interface UserService {
    void registerUser(UserRegisterDTO userRegisterDTO);
    TokenInfo loginUser(LoginRequestDTO loginRequestDTO);
    void logoutUser(String accessToken);
}
