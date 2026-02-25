package com.mudtool.plugin;

import com.mudtool.ai.SidecarClient;
import com.mudtool.config.MUDToolConfig;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * MUD Tool Modelio Plugin - Entry Point.
 *
 * This is the main module class that extends Modelio's AbstractJavaModule.
 * It manages the plugin lifecycle, registers menu commands, and coordinates
 * communication with the Python AI sidecar.
 *
 * In a full Modelio environment, this would extend AbstractJavaModule.
 * For standalone development, it provides the same interface pattern.
 */
public class MUDToolModule {

    private static final Logger LOG = LoggerFactory.getLogger(MUDToolModule.class);

    public static final String MODULE_NAME = "MUDTool";
    public static final String MODULE_VERSION = "0.1.0";

    private final MUDToolConfig config;
    private final SidecarClient sidecarClient;
    private Process sidecarProcess;
    private boolean initialized = false;

    public MUDToolModule() {
        this.config = MUDToolConfig.loadDefault();
        this.sidecarClient = new SidecarClient(config);
    }

    public MUDToolModule(MUDToolConfig config) {
        this.config = config;
        this.sidecarClient = new SidecarClient(config);
    }

    /**
     * Initialize the module - called when Modelio loads the plugin.
     * Starts the Python sidecar process and verifies connectivity.
     */
    public boolean init() {
        LOG.info("Initializing {} v{}", MODULE_NAME, MODULE_VERSION);

        try {
            // Start the Python sidecar
            if (config.isAutoStartSidecar()) {
                startSidecar();
            }

            // Verify sidecar connectivity
            if (sidecarClient.healthCheck()) {
                LOG.info("Sidecar connected successfully at {}", config.getSidecarUrl());
                initialized = true;
            } else {
                LOG.warn("Sidecar not reachable at {}. Some features will be unavailable.",
                        config.getSidecarUrl());
                initialized = true; // Allow offline features
            }

            // Register commands (in Modelio, these would be menu items)
            registerCommands();

            LOG.info("{} initialized successfully", MODULE_NAME);
            return true;

        } catch (Exception e) {
            LOG.error("Failed to initialize {}: {}", MODULE_NAME, e.getMessage(), e);
            return false;
        }
    }

    /**
     * Start the Python sidecar process.
     */
    private void startSidecar() {
        try {
            LOG.info("Starting Python sidecar...");
            ProcessBuilder pb = new ProcessBuilder(
                    config.getPythonPath(),
                    "-m", "mudtool.main"
            );
            pb.directory(new java.io.File(config.getSidecarWorkDir()));
            pb.environment().put("MUD_PORT", String.valueOf(config.getSidecarPort()));
            pb.environment().put("MUD_HOST", config.getSidecarHost());
            pb.redirectErrorStream(true);
            pb.inheritIO();

            sidecarProcess = pb.start();

            // Wait briefly for startup
            Thread.sleep(2000);

            LOG.info("Sidecar process started (PID: {})", sidecarProcess.pid());
        } catch (Exception e) {
            LOG.error("Failed to start sidecar: {}", e.getMessage(), e);
        }
    }

    /**
     * Register plugin commands in Modelio's menu system.
     */
    private void registerCommands() {
        LOG.info("Registering MUD Tool commands:");
        LOG.info("  - Import Requirements (from Excel/CSV/TXT)");
        LOG.info("  - Analyze Requirements (AI clustering)");
        LOG.info("  - Generate Diagrams (AI-driven MUD generation)");
        LOG.info("  - Validate Model (AUTOSAR rules check)");
        LOG.info("  - Show Traceability (requirement-to-model mapping)");
        LOG.info("  - Export Model (XMI/PlantUML)");
        LOG.info("  - AI Configuration (backend settings)");
    }

    /**
     * Shutdown the module - called when Modelio unloads the plugin.
     */
    public void uninit() {
        LOG.info("Shutting down {}", MODULE_NAME);

        if (sidecarProcess != null && sidecarProcess.isAlive()) {
            LOG.info("Stopping sidecar process...");
            sidecarProcess.destroy();
            try {
                sidecarProcess.waitFor(5, java.util.concurrent.TimeUnit.SECONDS);
            } catch (InterruptedException e) {
                sidecarProcess.destroyForcibly();
            }
        }

        initialized = false;
        LOG.info("{} shut down", MODULE_NAME);
    }

    // ── Accessors ────────────────────────────────────────

    public SidecarClient getSidecarClient() {
        return sidecarClient;
    }

    public MUDToolConfig getConfig() {
        return config;
    }

    public boolean isInitialized() {
        return initialized;
    }
}
