package com.mudtool.validation;

import com.fasterxml.jackson.databind.JsonNode;
import com.mudtool.ai.SidecarClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

/**
 * Validation Panel - displays validation results in the Modelio UI.
 *
 * Shows validation issues with severity, category, and auto-fix suggestions.
 * In the full Modelio plugin, this renders as a dedicated panel with
 * clickable issues that navigate to the offending model element.
 */
public class ValidationPanel {

    private static final Logger LOG = LoggerFactory.getLogger(ValidationPanel.class);

    private final SidecarClient sidecarClient;
    private List<ValidationIssueRecord> issues = new ArrayList<>();
    private boolean passed = true;

    public ValidationPanel(SidecarClient sidecarClient) {
        this.sidecarClient = sidecarClient;
    }

    /**
     * Run validation on a generation result.
     */
    public ValidationSummary validate(
            JsonNode generationResult,
            List<String> requirementIds
    ) throws IOException {
        LOG.info("Running validation...");

        JsonNode response = sidecarClient.validateModel(generationResult, requirementIds);
        return parseValidationReport(response);
    }

    /**
     * Parse a validation report (from generation or standalone validation).
     */
    public ValidationSummary parseValidationReport(JsonNode report) {
        issues.clear();
        passed = report.path("passed").asBoolean(true);

        JsonNode issuesArray = report.path("issues");
        if (issuesArray.isArray()) {
            for (JsonNode issue : issuesArray) {
                issues.add(new ValidationIssueRecord(
                        issue.path("rule_id").asText(),
                        issue.path("severity").asText(),
                        issue.path("category").asText(),
                        issue.path("message").asText(),
                        issue.path("element_id").asText(""),
                        issue.path("element_name").asText(""),
                        issue.path("diagram_name").asText(""),
                        issue.path("suggestion").asText(""),
                        issue.path("can_auto_fix").asBoolean(false)
                ));
            }
        }

        int errors = (int) issues.stream()
                .filter(i -> "error".equals(i.severity())).count();
        int warnings = (int) issues.stream()
                .filter(i -> "warning".equals(i.severity())).count();
        int infos = (int) issues.stream()
                .filter(i -> "info".equals(i.severity())).count();

        LOG.info("Validation: {} ({} errors, {} warnings, {} info)",
                passed ? "PASSED" : "FAILED", errors, warnings, infos);

        return new ValidationSummary(passed, errors, warnings, infos, issues);
    }

    public List<ValidationIssueRecord> getIssues() {
        return issues;
    }

    public List<ValidationIssueRecord> getErrors() {
        return issues.stream()
                .filter(i -> "error".equals(i.severity()))
                .toList();
    }

    public boolean isPassed() {
        return passed;
    }

    // ── Inner Types ──────────────────────────────────

    public record ValidationIssueRecord(
            String ruleId,
            String severity,
            String category,
            String message,
            String elementId,
            String elementName,
            String diagramName,
            String suggestion,
            boolean canAutoFix
    ) {}

    public record ValidationSummary(
            boolean passed,
            int errorCount,
            int warningCount,
            int infoCount,
            List<ValidationIssueRecord> issues
    ) {
        public String summary() {
            return String.format("Validation %s: %d errors, %d warnings, %d info",
                    passed ? "PASSED" : "FAILED", errorCount, warningCount, infoCount);
        }
    }
}
