package com.mudtool.ui;

import com.fasterxml.jackson.databind.JsonNode;
import com.mudtool.ai.SidecarClient;
import com.mudtool.config.MUDToolConfig;
import com.mudtool.generator.DiagramGenerator;
import com.mudtool.import_module.RequirementBrowser;
import com.mudtool.trace.TraceabilityMatrix;
import com.mudtool.validation.ValidationPanel;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.io.IOException;
import java.util.List;

/**
 * MUD Tool Workflow - orchestrates the complete end-to-end workflow.
 *
 * Provides a high-level API for the typical MUD tool workflow:
 * 1. Import requirements
 * 2. Analyze and cluster
 * 3. Generate diagrams
 * 4. Validate
 * 5. Review (human-in-the-loop)
 * 6. Export
 *
 * This class ties together all plugin components and can be used
 * from Modelio menu actions or programmatically.
 */
public class MUDToolWorkflow {

    private static final Logger LOG = LoggerFactory.getLogger(MUDToolWorkflow.class);

    private final SidecarClient sidecarClient;
    private final RequirementBrowser requirementBrowser;
    private final DiagramGenerator diagramGenerator;
    private final ValidationPanel validationPanel;
    private final TraceabilityMatrix traceabilityMatrix;

    private JsonNode lastGenerationResult;

    public MUDToolWorkflow(MUDToolConfig config) {
        this.sidecarClient = new SidecarClient(config);
        this.requirementBrowser = new RequirementBrowser(sidecarClient);
        this.diagramGenerator = new DiagramGenerator(sidecarClient);
        this.validationPanel = new ValidationPanel(sidecarClient);
        this.traceabilityMatrix = new TraceabilityMatrix(sidecarClient);
    }

    /**
     * Execute the full MUD generation workflow.
     *
     * @param requirementFile Excel/CSV/TXT/MD file with requirements
     * @param diagramTypes Diagram types to generate
     * @param outputPath Path for XMI export
     * @return Workflow result summary
     */
    public WorkflowResult executeFullWorkflow(
            File requirementFile,
            List<String> diagramTypes,
            String outputPath
    ) throws IOException {
        LOG.info("=== Starting MUD Tool Full Workflow ===");

        // Step 1: Import requirements
        LOG.info("Step 1: Importing requirements from {}", requirementFile.getName());
        var importResult = requirementBrowser.importFromFile(requirementFile);
        if (!importResult.success()) {
            return new WorkflowResult(false,
                    "Import failed: " + String.join(", ", importResult.errors()),
                    null, null, null);
        }
        LOG.info("  Imported {} requirements", importResult.importedCount());

        // Step 2: Analyze requirements
        LOG.info("Step 2: Analyzing requirements...");
        JsonNode analysis = diagramGenerator.analyzeRequirements(
                requirementBrowser.getCurrentRequirementSet()
        );
        LOG.info("  Analysis complete");

        // Step 3: Generate diagrams
        LOG.info("Step 3: Generating {} diagram(s)...", diagramTypes.size());
        var genOutput = diagramGenerator.generate(
                requirementBrowser.getCurrentRequirementSet(),
                diagramTypes,
                null
        );
        lastGenerationResult = genOutput.result();
        LOG.info("  {}", genOutput.summary());

        // Step 4: Validate
        LOG.info("Step 4: Validating generated models...");
        var validationSummary = validationPanel.parseValidationReport(
                genOutput.validationReport()
        );
        LOG.info("  {}", validationSummary.summary());

        // Step 5: Export
        LOG.info("Step 5: Exporting to XMI...");
        JsonNode exportResult = null;
        if (outputPath != null && genOutput.validationPassed()) {
            exportResult = sidecarClient.exportModel(
                    genOutput.result(), outputPath, "xmi", "MUD_Generated"
            );
            LOG.info("  Exported to {}", outputPath);
        }

        // Step 6: Traceability
        LOG.info("Step 6: Loading traceability matrix...");
        var traceData = traceabilityMatrix.loadMatrix(
                requirementBrowser.getAllRequirementIds()
        );
        if (traceData.coverage() != null) {
            LOG.info("  {}", traceData.coverage().summary());
        }

        LOG.info("=== MUD Tool Workflow Complete ===");

        return new WorkflowResult(
                true,
                genOutput.summary(),
                importResult,
                genOutput,
                validationSummary
        );
    }

    // ── Individual Step Access ───────────────────────

    public RequirementBrowser getRequirementBrowser() {
        return requirementBrowser;
    }

    public DiagramGenerator getDiagramGenerator() {
        return diagramGenerator;
    }

    public ValidationPanel getValidationPanel() {
        return validationPanel;
    }

    public TraceabilityMatrix getTraceabilityMatrix() {
        return traceabilityMatrix;
    }

    public JsonNode getLastGenerationResult() {
        return lastGenerationResult;
    }

    // ── Result Type ─────────────────────────────────

    public record WorkflowResult(
            boolean success,
            String message,
            RequirementBrowser.ImportResult importResult,
            DiagramGenerator.GenerationOutput generationOutput,
            ValidationPanel.ValidationSummary validationSummary
    ) {}
}
