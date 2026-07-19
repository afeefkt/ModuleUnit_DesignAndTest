package com.mudtool.ai;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import com.mudtool.config.MUDToolConfig;
import okhttp3.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.io.IOException;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;

/**
 * HTTP client for communicating with the Python FastAPI sidecar.
 *
 * Handles all API calls: requirement import, AI generation, validation,
 * export, and traceability queries.
 */
public class SidecarClient {

    private static final Logger LOG = LoggerFactory.getLogger(SidecarClient.class);
    private static final MediaType JSON_TYPE = MediaType.parse("application/json; charset=utf-8");

    private final MUDToolConfig config;
    private final OkHttpClient httpClient;
    private final ObjectMapper objectMapper;

    public SidecarClient(MUDToolConfig config) {
        this.config = config;
        this.httpClient = new OkHttpClient.Builder()
                .connectTimeout(Duration.ofMillis(config.getConnectionTimeoutMs()))
                .readTimeout(Duration.ofMillis(config.getReadTimeoutMs()))
                .writeTimeout(Duration.ofMillis(config.getReadTimeoutMs()))
                .build();
        this.objectMapper = new ObjectMapper()
                .registerModule(new JavaTimeModule())
                .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
    }

    // ── Health Check ─────────────────────────────────

    /**
     * Check if the sidecar is running and healthy.
     */
    public boolean healthCheck() {
        try {
            Request request = new Request.Builder()
                    .url(config.getSidecarUrl() + "/health")
                    .get()
                    .build();

            try (Response response = httpClient.newCall(request).execute()) {
                if (response.isSuccessful() && response.body() != null) {
                    JsonNode body = objectMapper.readTree(response.body().string());
                    return "ok".equals(body.path("status").asText());
                }
            }
        } catch (Exception e) {
            LOG.debug("Sidecar health check failed: {}", e.getMessage());
        }
        return false;
    }

    // ── Requirement Import ───────────────────────────

    /**
     * Import requirements from a file by uploading to the sidecar.
     *
     * @param file Excel, CSV, TXT, or Markdown file
     * @return JSON response with imported requirements
     */
    public JsonNode importRequirements(File file) throws IOException {
        String mediaType = guessMediaType(file.getName());

        RequestBody fileBody = RequestBody.create(file,
                MediaType.parse(mediaType));

        MultipartBody body = new MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart("file", file.getName(), fileBody)
                .build();

        Request request = new Request.Builder()
                .url(config.getSidecarUrl() + "/requirements/import")
                .post(body)
                .build();

        return executeRequest(request);
    }

    /**
     * Import requirements from raw text (for quick testing).
     *
     * @param text Requirement text content
     * @param format Format: txt, csv, or md
     */
    public JsonNode importRequirementsText(String text, String format) throws IOException {
        RequestBody body = new FormBody.Builder()
                .add("requirements_text", text)
                .add("format", format)
                .build();

        Request request = new Request.Builder()
                .url(config.getSidecarUrl() + "/requirements/import/text")
                .post(body)
                .build();

        return executeRequest(request);
    }

    // ── AI Analysis ──────────────────────────────────

    /**
     * Analyze requirements: cluster into modules, identify interfaces.
     */
    public JsonNode analyzeRequirements(JsonNode requirementSet) throws IOException {
        Map<String, Object> payload = Map.of("requirements", requirementSet);

        return postJson("/analyze", payload);
    }

    // ── Diagram Generation ───────────────────────────

    /**
     * Generate UML diagrams from requirements using AI.
     *
     * @param requirementSet The imported requirement set
     * @param diagramTypes List of types: "sequence", "state_machine", "class", "component"
     * @param moduleContext Optional module context string
     * @param applyMapping Whether to apply AUTOSAR mapping
     */
    public JsonNode generateDiagrams(
            JsonNode requirementSet,
            List<String> diagramTypes,
            String moduleContext,
            boolean applyMapping
    ) throws IOException {
        Map<String, Object> payload = new java.util.HashMap<>();
        payload.put("requirements", requirementSet);
        payload.put("diagram_types", diagramTypes);
        payload.put("apply_autosar_mapping", applyMapping);
        if (moduleContext != null) {
            payload.put("module_context", moduleContext);
        }

        return postJson("/generate", payload);
    }

    /**
     * Async version of generateDiagrams for non-blocking UI.
     */
    public CompletableFuture<JsonNode> generateDiagramsAsync(
            JsonNode requirementSet,
            List<String> diagramTypes,
            String moduleContext,
            boolean applyMapping
    ) {
        return CompletableFuture.supplyAsync(() -> {
            try {
                return generateDiagrams(requirementSet, diagramTypes, moduleContext, applyMapping);
            } catch (IOException e) {
                throw new RuntimeException("Generation failed: " + e.getMessage(), e);
            }
        });
    }

    // ── Validation ───────────────────────────────────

    /**
     * Validate generated models against AUTOSAR rules.
     */
    public JsonNode validateModel(JsonNode generationResult, List<String> requirementIds)
            throws IOException {
        Map<String, Object> payload = new java.util.HashMap<>();
        payload.put("result", generationResult);
        if (requirementIds != null) {
            payload.put("requirement_ids", requirementIds);
        }

        return postJson("/validate", payload);
    }

    // ── Export ────────────────────────────────────────

    /**
     * Export generated models to XMI or PlantUML format.
     */
    public JsonNode exportModel(
            JsonNode generationResult,
            String outputPath,
            String format,
            String modelName
    ) throws IOException {
        Map<String, Object> payload = Map.of(
                "result", generationResult,
                "output_path", outputPath,
                "format", format,
                "model_name", modelName
        );

        return postJson("/export", payload);
    }

    // ── Traceability ─────────────────────────────────

    /**
     * Get the full traceability matrix.
     */
    public JsonNode getTraceability(String requirementIds) throws IOException {
        String url = config.getSidecarUrl() + "/traceability";
        if (requirementIds != null && !requirementIds.isEmpty()) {
            url += "?requirement_ids=" + requirementIds;
        }

        Request request = new Request.Builder()
                .url(url)
                .get()
                .build();

        return executeRequest(request);
    }

    /**
     * Get traces for a specific requirement.
     */
    public JsonNode getTracesForRequirement(String reqId) throws IOException {
        Request request = new Request.Builder()
                .url(config.getSidecarUrl() + "/traceability/requirement/" + reqId)
                .get()
                .build();

        return executeRequest(request);
    }

    /**
     * Accept a model element (human review approval).
     */
    public JsonNode acceptElement(String elementId, String acceptedBy) throws IOException {
        Map<String, String> payload = Map.of(
                "element_id", elementId,
                "accepted_by", acceptedBy
        );

        return postJson("/traceability/accept", payload);
    }

    // ── Configuration ────────────────────────────────

    /**
     * Get current sidecar configuration.
     */
    public JsonNode getConfiguration() throws IOException {
        Request request = new Request.Builder()
                .url(config.getSidecarUrl() + "/config")
                .get()
                .build();

        return executeRequest(request);
    }

    // ── Internal Helpers ─────────────────────────────

    private JsonNode postJson(String path, Object payload) throws IOException {
        String jsonBody = objectMapper.writeValueAsString(payload);

        Request request = new Request.Builder()
                .url(config.getSidecarUrl() + path)
                .post(RequestBody.create(jsonBody, JSON_TYPE))
                .build();

        return executeRequest(request);
    }

    private JsonNode executeRequest(Request request) throws IOException {
        LOG.debug("HTTP {} {}", request.method(), request.url());

        try (Response response = httpClient.newCall(request).execute()) {
            String body = response.body() != null ? response.body().string() : "{}";

            if (!response.isSuccessful()) {
                LOG.error("Sidecar error {}: {}", response.code(), body);
                throw new IOException(String.format(
                        "Sidecar request failed (HTTP %d): %s", response.code(), body));
            }

            return objectMapper.readTree(body);
        }
    }

    private String guessMediaType(String filename) {
        String lower = filename.toLowerCase();
        if (lower.endsWith(".xlsx") || lower.endsWith(".xls")) {
            return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
        } else if (lower.endsWith(".csv")) {
            return "text/csv";
        } else if (lower.endsWith(".md")) {
            return "text/markdown";
        }
        return "text/plain";
    }
}
