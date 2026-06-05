package com.example.bitcomputer.controller;

import java.util.List;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.authentication.AnonymousAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.example.bitcomputer.Repository.EmployeeRepository;
import com.example.bitcomputer.entity.Employee;
import com.example.bitcomputer.entity.Role;
import com.example.bitcomputer.jwt.JwtTokenProvider;
import com.example.bitcomputer.model.RoleUpdateDTO;
import com.example.bitcomputer.model.UserRegisterDTO;

@RestController
@RequestMapping("/api/super")
public class SuperUserController {

    private final EmployeeRepository employeeRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtTokenProvider jwtTokenProvider;

    public SuperUserController(EmployeeRepository employeeRepository,
                               PasswordEncoder passwordEncoder,
                               JwtTokenProvider jwtTokenProvider) {
        this.employeeRepository = employeeRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtTokenProvider = jwtTokenProvider;
    }

    @PutMapping("/set_role/{id}")
    public ResponseEntity<String> setRole(
            @PathVariable int id,
            @RequestBody RoleUpdateDTO request,
            @RequestHeader(value = "Authorization", required = false) String authHeader) {

        ResponseEntity<String> authError = validateSuperUser(authHeader);
        if (authError != null) {
            return authError;
        }

        Employee employee = employeeRepository.findById(id).orElse(null);
        if (employee == null) {
            return ResponseEntity.notFound().build();
        }

        if (request == null || request.getRole() == null || request.getRole().isBlank()) {
            return ResponseEntity.badRequest().body("role 값이 필요합니다.");
        }

        Role newRole;
        try {
            newRole = Role.valueOf(request.getRole());
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body("유효하지 않은 role 값입니다.");
        }

        employee.setRole(newRole);
        employeeRepository.save(employee);
        return ResponseEntity.ok("Role set successfully");
    }

    @PostMapping("/create_user")
    public ResponseEntity<String> createUser(
            @RequestBody UserRegisterDTO request,
            @RequestHeader(value = "Authorization", required = false) String authHeader) {

        ResponseEntity<String> authError = validateSuperUser(authHeader);
        if (authError != null) {
            return authError;
        }

        if (request == null || request.getUsername() == null || request.getUsername().isBlank()
                || request.getPassword() == null || request.getPassword().isBlank()
                || request.getName() == null || request.getName().isBlank()) {
            return ResponseEntity.badRequest().body("name, username, password 값이 필요합니다.");
        }

        if (employeeRepository.findByUsername(request.getUsername()) != null) {
            return ResponseEntity.status(HttpStatus.CONFLICT).body("Username already exists");
        }

        Role role;
        try {
            role = parseRole(request.getRole());
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(e.getMessage());
        }
        Employee employee = new Employee();
        employee.setName(request.getName().trim());
        employee.setUsername(request.getUsername().trim());
        employee.setPassword(passwordEncoder.encode(request.getPassword()));
        employee.setDeptId(request.getDeptId() > 0 ? request.getDeptId() : 1);
        employee.setRole(role);
        employeeRepository.save(employee);
        return ResponseEntity.status(HttpStatus.CREATED).body("User created successfully");
    }

    @GetMapping("/get_all_users")
    public ResponseEntity<?> getAllEmployees(
            @RequestHeader(value = "Authorization", required = false) String authHeader) {
        ResponseEntity<String> authError = validateSuperUser(authHeader);
        if (authError != null) {
            return authError;
        }
        return ResponseEntity.ok(employeeRepository.findAll());
    }

    private ResponseEntity<String> validateSuperUser(String authHeader) {
        Employee requester = extractEmployee(authHeader);
        if (requester == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body("인증 정보가 없습니다.");
        }
        if (requester.getRole() != Role.SUPER_USER) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).body("SUPER_USER만 접근 가능합니다.");
        }
        return null;
    }

    private Employee extractEmployee(String authHeader) {
        if (authHeader != null && authHeader.startsWith("Bearer ")) {
            String token = authHeader.substring(7);
            if (!jwtTokenProvider.validateToken(token)) {
                return null;
            }
            return employeeRepository.findByUsername(jwtTokenProvider.extractUsername(token));
        }

        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication == null || authentication instanceof AnonymousAuthenticationToken) {
            return null;
        }
        return employeeRepository.findByUsername(authentication.getName());
    }

    private Role parseRole(String roleValue) {
        if (roleValue == null || roleValue.isBlank()) {
            return Role.DEFAULT;
        }
        try {
            return Role.valueOf(roleValue.trim().toUpperCase());
        } catch (IllegalArgumentException e) {
            throw new IllegalArgumentException("유효하지 않은 role 값입니다.");
        }
    }
}
