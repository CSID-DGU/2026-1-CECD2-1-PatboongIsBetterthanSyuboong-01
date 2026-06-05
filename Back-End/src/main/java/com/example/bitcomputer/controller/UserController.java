package com.example.bitcomputer.controller;

import com.example.bitcomputer.jwt.JwtTokenProvider;
import com.example.bitcomputer.jwt.TokenInfo;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import com.example.bitcomputer.service.UserService;
import com.example.bitcomputer.model.UserRegisterDTO;
import com.example.bitcomputer.model.LoginRequestDTO;

@RestController
@RequestMapping("/api/user")
public class UserController {

    private final UserService userService;
    private final JwtTokenProvider jwtTokenProvider;

    public UserController(UserService userService, JwtTokenProvider jwtTokenProvider) {
        this.userService = userService;
        this.jwtTokenProvider = jwtTokenProvider;
    }

    @ExceptionHandler(IllegalArgumentException.class)
    @ResponseStatus(HttpStatus.CONFLICT)
    public ResponseEntity<String> handleIllegalArgumentException(IllegalArgumentException e) {
        return ResponseEntity.status(HttpStatus.CONFLICT).body(e.getMessage());
    }

    @PostMapping("/register")
    public ResponseEntity<String> registerUser(@RequestBody UserRegisterDTO userRegisterDTO) {
        try {
            userService.registerUser(userRegisterDTO);
            return ResponseEntity.status(HttpStatus.CREATED).body("User registered successfully");
        } catch (IllegalArgumentException e) {
            return ResponseEntity.status(HttpStatus.CONFLICT).body(e.getMessage());
        }
    }

    @PostMapping("/login")
    public ResponseEntity<TokenInfo> loginUser(@RequestBody LoginRequestDTO loginRequestDTO) {
        TokenInfo tokenInfo = userService.loginUser(loginRequestDTO);
        if (tokenInfo != null) {
            return ResponseEntity.ok(tokenInfo);
        } else {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(null);
        }
    }

    @PostMapping("/logout")
    public ResponseEntity<String> logout(@RequestHeader("Authorization") String accessToken) {
        try {
            String token = accessToken.replace("Bearer ", "");
            
            // 유효성 검사
            if (!jwtTokenProvider.validateToken(token)) {
                return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body("Invalid token");
            }
            
            // 서비스 계층에서 로그아웃 처리
            userService.logoutUser(token);
            return ResponseEntity.ok("Logged out successfully");

        } catch (IllegalArgumentException e) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body("Invalid token");
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body("An error occurred during logout");
        }
    }
}
