package com.example.bitcomputer.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;
import java.util.Map;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonIgnoreProperties(ignoreUnknown = true)
public class ValidationAgentResponse {
    private String overallStatus;
    private String summary;
    private List<Map<String, Object>> checks;
    private List<Map<String, Object>> suspectedIssues;
    private List<String> suggestedReviewItems;
    private List<Map<String, Object>> candidatePrescriptions;

    @JsonProperty("shouldNotifyDoctor")
    private Boolean shouldNotifyDoctor;

    @JsonProperty("shouldBlockAutoPrescription")
    private Boolean shouldBlockAutoPrescription;
}
