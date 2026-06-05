package com.example.bitcomputer.util;

import com.example.bitcomputer.service.DiagnoseService;
import com.example.bitcomputer.service.DiseaseService;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

import java.io.File;

/**
 * 로컬에서 엑셀 파일을 업로드하여 DB에 저장하는 유틸리티 클래스
 * 
 * 사용 방법:
 * 1. 애플리케이션 실행 시 명령줄 인자로 파일 경로와 타입을 전달
 *    예: java -jar app.jar --upload=disease --file=path/to/disease.xlsx
 *    예: java -jar app.jar --upload=diagnose --file=path/to/diagnose.xlsx
 * 
 * 2. 또는 IDE에서 실행 시 Program arguments에 추가
 *    --upload=disease --file=C:/path/to/disease.xlsx
 */
@Component
public class ExcelUploadUtil implements CommandLineRunner {

    private final DiseaseService diseaseService;
    private final DiagnoseService diagnoseService;

    public ExcelUploadUtil(DiseaseService diseaseService, DiagnoseService diagnoseService) {
        this.diseaseService = diseaseService;
        this.diagnoseService = diagnoseService;
    }

    @Override
    public void run(String... args) {
        if (args.length == 0) {
            return; // 인자가 없으면 아무것도 하지 않음
        }

        String uploadType = null;
        String filePath = null;

        // 명령줄 인자 파싱
        for (String arg : args) {
            if (arg.startsWith("--upload=")) {
                uploadType = arg.substring("--upload=".length()).trim();
            } else if (arg.startsWith("--file=")) {
                filePath = arg.substring("--file=".length()).trim();
            }
        }

        // 업로드 타입과 파일 경로가 모두 제공된 경우에만 실행
        if (uploadType != null && filePath != null) {
            File file = new File(filePath);
            
            try {
                int count = 0;
                
                if ("disease".equalsIgnoreCase(uploadType)) {
                    count = diseaseService.uploadFromExcel(file);
                    System.out.println("Disease 엑셀 업로드 완료: " + count + "개 레코드가 저장되었습니다.");
                } else if ("diagnose".equalsIgnoreCase(uploadType)) {
                    count = diagnoseService.uploadFromExcel(file);
                    System.out.println("Diagnose 엑셀 업로드 완료: " + count + "개 레코드가 저장되었습니다.");
                } else {
                    System.err.println("잘못된 업로드 타입입니다. 'disease' 또는 'diagnose'를 사용하세요.");
                    System.err.println("사용법: --upload=disease --file=파일경로");
                    System.err.println("      또는 --upload=diagnose --file=파일경로");
                }
            } catch (Exception e) {
                System.err.println("엑셀 업로드 중 오류 발생: " + e.getMessage());
                e.printStackTrace();
            }
        } else if (uploadType != null || filePath != null) {
            System.err.println("업로드 타입과 파일 경로를 모두 제공해야 합니다.");
            System.err.println("사용법: --upload=disease --file=파일경로");
            System.err.println("      또는 --upload=diagnose --file=파일경로");
        }
    }
}

