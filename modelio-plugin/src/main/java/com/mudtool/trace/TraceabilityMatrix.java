package com.mudtool.trace;

import com.fasterxml.jackson.databind.JsonNode;
import com.mudtool.ai.SidecarClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

/**
 * Traceability Matrix - requirement-to-model element mapping UI.
 *
 * Shows bidirectional traceability with coverage analysis.
 * In the full Modelio plugin, this renders as a matrix panel
 * with clickable links to model elements and requirements.
 */
public class TraceabilityMatrix {

    private static final Logger LOG = LoggerFactory.getLogger(TraceabilityMatrix.class);

    private final SidecarClient sidecarClient;

    public TraceabilityMatrix(SidecarClient sidecarClient) {
        this.sidecarClient = sidecarClient;
    }

    /**
     * Load the full traceability matrix from the sidecar.
     */
    public TraceabilityData loadMatrix(List<String> requirementIds) throws IOException {
        String ids = requirementIds != null ? String.join(",", requirementIds) : null;
        JsonNode response = sidecarClient.getTraceability(ids);

        List<TraceEntry> entries = new ArrayList<>();
        JsonNode matrix = response.path("matrix");
        if (matrix.isArray()) {
            for (JsonNode row : matrix) {
                String reqId = row.path("requirement_id").asText();
                List<TraceElement> elements = new ArrayList<>();

                JsonNode elementsArray = row.path("elements");
                if (elementsArray.isArray()) {
                    for (JsonNode elem : elementsArray) {
                        elements.add(new TraceElement(
                                elem.path("element_name").asText(),
                                elem.path("element_type").asText(),
                                elem.path("diagram_type").asText(),
                                elem.path("diagram_name").asText(),
                                elem.path("confidence").asDouble(),
                                elem.path("accepted").asBoolean()
                        ));
                    }
                }

                entries.add(new TraceEntry(reqId, elements));
            }
        }

        // Coverage info
        CoverageInfo coverage = null;
        JsonNode coverageNode = response.path("coverage");
        if (!coverageNode.isMissingNode()) {
            List<String> uncovered = new ArrayList<>();
            coverageNode.path("uncovered_ids").forEach(n -> uncovered.add(n.asText()));

            coverage = new CoverageInfo(
                    coverageNode.path("total_requirements").asInt(),
                    coverageNode.path("covered_requirements").asInt(),
                    coverageNode.path("uncovered_requirements").asInt(),
                    coverageNode.path("coverage_percentage").asDouble(),
                    uncovered
            );
        }

        return new TraceabilityData(entries, coverage);
    }

    /**
     * Get traces for a single requirement.
     */
    public List<TraceElement> getTracesForRequirement(String reqId) throws IOException {
        JsonNode response = sidecarClient.getTracesForRequirement(reqId);
        List<TraceElement> elements = new ArrayList<>();

        JsonNode traces = response.path("traces");
        if (traces.isArray()) {
            for (JsonNode trace : traces) {
                elements.add(new TraceElement(
                        trace.path("element_name").asText(),
                        trace.path("element_type").asText(),
                        trace.path("diagram_type").asText(),
                        trace.path("diagram_name").asText(),
                        trace.path("confidence").asDouble(),
                        trace.path("accepted").asBoolean()
                ));
            }
        }

        return elements;
    }

    /**
     * Accept a model element as reviewed.
     */
    public void acceptElement(String elementId, String reviewer) throws IOException {
        sidecarClient.acceptElement(elementId, reviewer);
        LOG.info("Element '{}' accepted by '{}'", elementId, reviewer);
    }

    // ── Inner Types ──────────────────────────────────

    public record TraceElement(
            String elementName,
            String elementType,
            String diagramType,
            String diagramName,
            double confidence,
            boolean accepted
    ) {}

    public record TraceEntry(
            String requirementId,
            List<TraceElement> elements
    ) {}

    public record CoverageInfo(
            int totalRequirements,
            int coveredRequirements,
            int uncoveredRequirements,
            double coveragePercentage,
            List<String> uncoveredIds
    ) {
        public String summary() {
            return String.format("Coverage: %.1f%% (%d/%d requirements covered)",
                    coveragePercentage, coveredRequirements, totalRequirements);
        }
    }

    public record TraceabilityData(
            List<TraceEntry> entries,
            CoverageInfo coverage
    ) {}
}
