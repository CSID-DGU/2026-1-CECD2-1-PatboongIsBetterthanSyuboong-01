package com.example.bitcomputer.Repository;

import com.example.bitcomputer.entity.Dept;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface DeptRepository extends JpaRepository<Dept, Integer> {
    List<Dept> findByDeptContainingIgnoreCase(String dept);
}
