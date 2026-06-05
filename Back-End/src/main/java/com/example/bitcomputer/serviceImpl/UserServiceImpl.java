package com.example.bitcomputer.serviceImpl;

import com.example.bitcomputer.model.UserRegisterDTO;
import com.example.bitcomputer.jwt.TokenInfo;
import com.example.bitcomputer.model.LoginRequestDTO;
import com.example.bitcomputer.service.UserService;
import com.example.bitcomputer.Repository.UserRepository;
import com.example.bitcomputer.entity.Employee;
import com.example.bitcomputer.entity.Role;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import com.example.bitcomputer.jwt.JwtTokenProvider;

@Service
public class UserServiceImpl implements UserService {
    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtTokenProvider jwtTokenProvider;
    private final TokenBlacklistService tokenBlacklistService;

    public UserServiceImpl(UserRepository userRepository, 
    PasswordEncoder passwordEncoder, JwtTokenProvider jwtTokenProvider, 
    TokenBlacklistService tokenBlacklistService) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtTokenProvider = jwtTokenProvider;
        this.tokenBlacklistService = tokenBlacklistService;
    }

    @Override
    public void registerUser(UserRegisterDTO userRegisterDTO) {
        // TODO: Implement user registration logic
        Employee employee = new Employee();
        if (userRepository.findByUsername(userRegisterDTO.getUsername()) != null) {
            throw new IllegalArgumentException("Username already exists");
        }
        employee.setName(userRegisterDTO.getName());
        int requestedDeptId = userRegisterDTO.getDeptId();
        int defaultDeptId = 1; // 더미 부서 ID
        employee.setDeptId(requestedDeptId > 0 ? requestedDeptId : defaultDeptId);
        String requestedRole = userRegisterDTO.getRole();
        Role role = Role.DEFAULT;
        if (requestedRole != null) {
            try {
                role = Role.valueOf(requestedRole.toUpperCase());
            } catch (IllegalArgumentException ex) {
                throw new IllegalArgumentException("Invalid role: " + requestedRole);
            }
        }
        employee.setRole(role);
        employee.setUsername(userRegisterDTO.getUsername());
        // 비밀번호 암호화 (SecurityConfig에서 정의한 PasswordEncoder 사용)
        employee.setPassword(passwordEncoder.encode(userRegisterDTO.getPassword()));
        userRepository.save(employee);
    }

    @Override
    public TokenInfo loginUser(LoginRequestDTO loginRequestDTO) {
        // TODO Auto-generated method stub
        Employee employee = userRepository.findByUsername(loginRequestDTO.getUsername());
        if (employee == null) {
            throw new IllegalArgumentException("Invalid username or password");
        }
        if (!passwordEncoder.matches(loginRequestDTO.getPassword(), employee.getPassword())) {
            throw new IllegalArgumentException("Invalid username or password");
        }
        String accessToken = jwtTokenProvider.generateAccessToken(employee.getUsername());
        String refreshToken = jwtTokenProvider.generateRefreshToken(employee.getUsername());
        return new TokenInfo("Bearer", accessToken, refreshToken);
    }

    @Override
    public void logoutUser(String accessToken) {
        // 만료 시간을 밀리초에서 초로 변환하여 전달
        long expirationTime = (jwtTokenProvider.getExpiration(accessToken) - System.currentTimeMillis()) / 1000;
        if (expirationTime > 0) {
            tokenBlacklistService.blacklistToken(accessToken, expirationTime);
        }
    }
}
