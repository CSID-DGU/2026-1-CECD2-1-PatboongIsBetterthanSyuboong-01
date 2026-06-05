package com.example.bitcomputer.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

@Configuration
public class WebMvcConfig implements WebMvcConfigurer {

    @Override
    public void addResourceHandlers(ResourceHandlerRegistry registry) {
        // 프로젝트 루트 찾기
        // 스프링은 Back-End 폴더에서 실행되므로, 상위 디렉토리에서 BitComputer 찾기
        Path currentPath = Paths.get("").toAbsolutePath();
        
        Path bitComputerPath = null;
        
        // 현재 경로가 Back-End인 경우
        if (currentPath.getFileName().toString().equals("Back-End")) {
            bitComputerPath = currentPath.getParent();
        } else {
            // 현재 경로에서 BitComputer 찾기
            bitComputerPath = currentPath.resolve("BitComputer");
            if (!Files.exists(bitComputerPath) || !Files.isDirectory(bitComputerPath)) {
                Path parent = currentPath.getParent();
                if (parent != null) {
                    bitComputerPath = parent.resolve("BitComputer");
                    if (!Files.exists(bitComputerPath) || !Files.isDirectory(bitComputerPath)) {
                        bitComputerPath = parent; // parent가 이미 BitComputer일 수 있음
                    }
                }
            }
        }
        
        if (bitComputerPath == null || !Files.exists(bitComputerPath)) {
            System.err.println("경고: BitComputer 폴더를 찾을 수 없습니다. 현재 경로: " + currentPath);
            return;
        }
        
        // 여러 가능한 images 폴더 경로 확인
        // 1. Back-End/images (Flask가 overlay 이미지를 저장하는 경로)
        Path backEndImagesPath = bitComputerPath.resolve("Back-End").resolve("images");
        String backEndImagesPathStr = backEndImagesPath.toAbsolutePath().toString().replace("\\", "/");
        
        // 2. Back-End/BitComputer/images (스프링이 원본 이미지를 저장하는 경로)
        Path backEndBitComputerImagesPath = bitComputerPath.resolve("Back-End").resolve("BitComputer").resolve("images");
        String backEndBitComputerImagesPathStr = backEndBitComputerImagesPath.toAbsolutePath().toString().replace("\\", "/");
        
        // 3. BitComputer/images (프로젝트 루트)
        Path imagesPath = bitComputerPath.resolve("images");
        String imagesPathStr = imagesPath.toAbsolutePath().toString().replace("\\", "/");
        
        System.out.println("[DEBUG] 정적 리소스 경로 설정:");
        System.out.println("  - Back-End/images: " + backEndImagesPathStr + " (존재: " + Files.exists(backEndImagesPath) + ")");
        System.out.println("  - Back-End/BitComputer/images: " + backEndBitComputerImagesPathStr + " (존재: " + Files.exists(backEndBitComputerImagesPath) + ")");
        System.out.println("  - BitComputer/images: " + imagesPathStr + " (존재: " + Files.exists(imagesPath) + ")");
        
        // 정적 리소스 핸들러 등록 (여러 경로를 순서대로 확인)
        registry.addResourceHandler("/images/**")
                .addResourceLocations(
                    "file:" + backEndImagesPathStr + "/",
                    "file:" + backEndBitComputerImagesPathStr + "/",
                    "file:" + imagesPathStr + "/"
                );
    }
}

