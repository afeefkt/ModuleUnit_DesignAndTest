package com.mudtool.import_module;

import com.fasterxml.jackson.databind.JsonNode;
import com.mudtool.ai.SidecarClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

/**
 * Requirement Browser - manages requirement import and browsing.
 *
 * In the full Modelio plugin, this provides a panel showing imported
 * requirements with filtering, sorting, and selection for diagram generation.
 */
public class RequirementBrowser {

    private static final Logger LOG = LoggerFactory.getLogger(RequirementBrowser.class);

    private final SidecarClient sidecarClient;
    private JsonNode currentRequirementSet;
    private List<RequirementRecord> requirements = new ArrayList<>();

    public RequirementBrowser(SidecarClient sidecarClient) {
        this.sidecarClient = sidecarClient;
    }

    /**
     * Import requirements from a file.
     *
     * @param file Excel, CSV, TXT, or Markdown file
     * @return Import result with success/failure info
     */
    public ImportResult importFromFile(File file) throws IOException {
        LOG.info("Importing requirements from: {}", file.getName());

        JsonNode response = sidecarClient.importRequirements(file);

        currentRequirementSet = response.path("requirement_set");
        boolean success = response.path("success").asBoolean(false);

        // Parse requirements into records
        requirements.clear();
        JsonNode reqsArray = currentRequirementSet.path("requirements");
        if (reqsArray.isArray()) {
            for (JsonNode req : reqsArray) {
                requirements.add(new RequirementRecord(
                        req.path("req_id").asText(),
                        req.path("title").asText(),
                        req.path("description").asText(),
                        req.path("req_type").asText(),
                        req.path("safety_level").asText(""),
                        req.path("priority").asText(),
                        req.path("module_hint").asText("")
                ));
            }
        }

        // Collect warnings and errors
        List<String> warnings = new ArrayList<>();
        response.path("warnings").forEach(w -> warnings.add(w.asText()));
        List<String> errors = new ArrayList<>();
        response.path("errors").forEach(e -> errors.add(e.asText()));

        LOG.info("Imported {} requirements ({} warnings, {} errors)",
                requirements.size(), warnings.size(), errors.size());

        return new ImportResult(
                success,
                requirements.size(),
                response.path("rows_processed").asInt(),
                response.path("rows_skipped").asInt(),
                warnings,
                errors
        );
    }

    /**
     * Import requirements from raw text (quick testing).
     */
    public ImportResult importFromText(String text, String format) throws IOException {
        JsonNode response = sidecarClient.importRequirementsText(text, format);
        currentRequirementSet = response.path("requirement_set");

        requirements.clear();
        JsonNode reqsArray = currentRequirementSet.path("requirements");
        if (reqsArray.isArray()) {
            for (JsonNode req : reqsArray) {
                requirements.add(new RequirementRecord(
                        req.path("req_id").asText(),
                        req.path("title").asText(),
                        req.path("description").asText(),
                        req.path("req_type").asText(),
                        req.path("safety_level").asText(""),
                        req.path("priority").asText(),
                        req.path("module_hint").asText("")
                ));
            }
        }

        return new ImportResult(
                response.path("success").asBoolean(),
                requirements.size(), 0, 0,
                new ArrayList<>(), new ArrayList<>()
        );
    }

    /**
     * Get the current requirement set as JSON for API calls.
     */
    public JsonNode getCurrentRequirementSet() {
        return currentRequirementSet;
    }

    /**
     * Get all imported requirement records.
     */
    public List<RequirementRecord> getRequirements() {
        return requirements;
    }

    /**
     * Get requirement IDs for a specific type.
     */
    public List<String> getRequirementIdsByType(String type) {
        return requirements.stream()
                .filter(r -> r.type().equalsIgnoreCase(type))
                .map(RequirementRecord::id)
                .toList();
    }

    /**
     * Get all requirement IDs.
     */
    public List<String> getAllRequirementIds() {
        return requirements.stream()
                .map(RequirementRecord::id)
                .toList();
    }

    // ── Inner Types ──────────────────────────────────

    public record RequirementRecord(
            String id,
            String title,
            String description,
            String type,
            String safetyLevel,
            String priority,
            String moduleHint
    ) {}

    public record ImportResult(
            boolean success,
            int importedCount,
            int rowsProcessed,
            int rowsSkipped,
            List<String> warnings,
            List<String> errors
    ) {}
}
