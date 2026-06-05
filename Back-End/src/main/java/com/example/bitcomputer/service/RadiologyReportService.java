package com.example.bitcomputer.service;

import com.example.bitcomputer.model.RadiologyReportRequestDTO;
import com.example.bitcomputer.model.RadiologyAnalysisResponseDTO;

public interface RadiologyReportService {
    RadiologyAnalysisResponseDTO processRadiologyReport(RadiologyReportRequestDTO request);
    
    /**
     * 영상판독 요청을 DB에 저장하고 radiologyRequestId를 반환
     * 
     * @param request 영상판독 요청 정보 (임시 경로 포함 가능)
     * @return 생성된 radiologyRequestId
     */
    int createRadiologyReportRequest(RadiologyReportRequestDTO request);
    
    /**
     * 영상판독 요청의 이미지 경로를 업데이트
     * 
     * @param radiologyRequestId 영상판독 요청 ID
     * @param imagePath 새로운 이미지 경로
     */
    void updateImagePath(int radiologyRequestId, String imagePath);
}
