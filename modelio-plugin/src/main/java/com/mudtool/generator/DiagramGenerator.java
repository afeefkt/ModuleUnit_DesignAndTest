package com.mudtool.generator;

import com.fasterxml.jackson.databind.JsonNode;
import com.mudtool.ai.SidecarClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.util.List;
import java.util.concurrent.CompletableFuture;

/**
 * Diagram Generator - orchestrates AI-driven diagram generation.
 *
 * Communicates with the Python sidecar to generate UML diagrams
 * from imported requirements. In the full Modelio plugin, this
 * translates JSON-UML responses into Modelio model elements.
 */
public class DiagramGenerator {

    private static final Logger LOG = LoggerFactory.getLogger(DiagramGenerator.class);

    private final SidecarClient sidecarClient;

    public DiagramGenerator(SidecarClient sidecarClient) {
        this.sidecarClient = sidecarClient;
    }

    /**
     * Generate diagrams synchronously.
     *
     * @param requirementSet The requirement set JSON from import
     * @param diagramTypes Types to generate
     * @param moduleContext Optional module context
     * @return Generation result with diagrams and validation
     */
    public GenerationOutput generate(
            JsonNode requirementSet,
            List<String> diagramTypes,
            String moduleContext
    ) throws IOException {
        LOG.info("Starting diagram generation: types={}", diagramTypes);

        JsonNode response = sidecarClient.generateDiagrams(
                requirementSet, diagramTypes, moduleContext, true
        );

        return parseOutput(response);
    }

    /**
     * Generate diagrams asynchronously (non-blocking).
     */
    public CompletableFuture<GenerationOutput> generateAsync(
            JsonNode requirementSet,
            List<String> diagramTypes,
            String moduleContext
    ) {
        return sidecarClient.generateDiagramsAsync(
                requirementSet, diagramTypes, moduleContext, true
        ).thenApply(this::parseOutput);
    }

    /**
     * Analyze requirements to identify modules and interfaces.
     */
    public JsonNode analyzeRequirements(JsonNode requirementSet) throws IOException {
        LOG.info("Analyzing requirements for module clustering...");
        return sidecarClient.analyzeRequirements(requirementSet);
    }

    private GenerationOutput parseOutput(JsonNode response) {
        JsonNode result = response.path("result");
        JsonNode validation = response.path("validation_report");

        int diagramCount = 0;
        JsonNode diagrams = result.path("diagrams");
        if (diagrams.isArray()) {
            diagramCount = diagrams.size();
        }

        int errorCount = 0;
        int warningCount = 0;
        if (!validation.isMissingNode()) {
            errorCount = validation.path("error_count").asInt(0);
            warningCount = validation.path("warning_count").asInt(0);
        }

        boolean passed = validation.path("passed").asBoolean(true);
        int timeMs = result.path("total_generation_time_ms").asInt(0);

        LOG.info("Generation complete: {} diagrams in {}ms (validation: {})",
                diagramCount, timeMs, passed ? "PASSED" : "FAILED");

        return new GenerationOutput(
                result, validation, diagramCount, errorCount, warningCount, passed, timeMs
        );
    }

    // ── Result Type ─────────────────────────────────

    public record GenerationOutput(
            JsonNode result,
            JsonNode validationReport,
            int diagramCount,
            int errorCount,
            int warningCount,
            boolean validationPassed,
            int generationTimeMs
    ) {
        public String summary() {
            return String.format(
                    "%d diagrams generated in %dms | Validation: %s (%d errors, %d warnings)",
                    diagramCount, generationTimeMs,
                    validationPassed ? "PASSED" : "FAILED",
                    errorCount, warningCount
            );
        }
    }
}
