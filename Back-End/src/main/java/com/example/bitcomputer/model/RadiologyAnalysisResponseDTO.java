package com.example.bitcomputer.model;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.ArrayList;
import java.util.List;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class RadiologyAnalysisResponseDTO {
    private String heatmapUrl;
    private List<PredictedDisease> predictedDiseases = new ArrayList<>();
    private String warning;

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class PredictedDisease {
        private String disease;
        private double score;
        private String reason;
    }
}
