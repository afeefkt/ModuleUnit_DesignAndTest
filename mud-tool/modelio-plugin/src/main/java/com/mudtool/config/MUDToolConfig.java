package com.mudtool.config;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Properties;

/**
 * Configuration for the MUD Tool Modelio Plugin.
 *
 * Manages sidecar connection settings, AI configuration,
 * and plugin behavior preferences.
 */
public class MUDToolConfig {

    // Sidecar connection
    private String sidecarHost = "127.0.0.1";
    private int sidecarPort = 8042;
    private boolean autoStartSidecar = true;
    private String pythonPath = "python";
    private String sidecarWorkDir = ".";
    private int connectionTimeoutMs = 10_000;
    private int readTimeoutMs = 120_000;

    // AI settings
    private String aiBackend = "cloud";  // cloud, local, auto
    private double confidenceThreshold = 0.6;
    private int maxRetries = 3;

    // AUTOSAR naming
    private String swcNamingRegex = "^SWC_[A-Z][A-Za-z0-9_]+$";
    private String runnableNamingRegex = "^RE_[A-Z][A-Za-z0-9_]+$";
    private String portNamingRegex = "^(PP|RP)_[A-Z][A-Za-z0-9_]+$";

    // Export settings
    private String defaultExportFormat = "xmi";
    private String exportDirectory = "output";

    /**
     * Load default configuration from properties file or system defaults.
     */
    public static MUDToolConfig loadDefault() {
        MUDToolConfig config = new MUDToolConfig();

        // Try loading from properties file
        try (InputStream is = MUDToolConfig.class.getResourceAsStream("/mudtool.properties")) {
            if (is != null) {
                Properties props = new Properties();
                props.load(is);
                config.applyProperties(props);
            }
        } catch (IOException e) {
            // Use defaults
        }

        // Override with environment variables
        config.applyEnvironment();

        return config;
    }

    /**
     * Load configuration from a specific properties file.
     */
    public static MUDToolConfig loadFrom(Path propertiesFile) throws IOException {
        MUDToolConfig config = new MUDToolConfig();
        Properties props = new Properties();
        try (InputStream is = Files.newInputStream(propertiesFile)) {
            props.load(is);
        }
        config.applyProperties(props);
        config.applyEnvironment();
        return config;
    }

    private void applyProperties(Properties props) {
        sidecarHost = props.getProperty("mudtool.sidecar.host", sidecarHost);
        sidecarPort = Integer.parseInt(props.getProperty("mudtool.sidecar.port",
                String.valueOf(sidecarPort)));
        autoStartSidecar = Boolean.parseBoolean(props.getProperty("mudtool.sidecar.autostart",
                String.valueOf(autoStartSidecar)));
        pythonPath = props.getProperty("mudtool.python.path", pythonPath);
        sidecarWorkDir = props.getProperty("mudtool.sidecar.workdir", sidecarWorkDir);
        aiBackend = props.getProperty("mudtool.ai.backend", aiBackend);
        confidenceThreshold = Double.parseDouble(props.getProperty("mudtool.ai.confidence_threshold",
                String.valueOf(confidenceThreshold)));
        maxRetries = Integer.parseInt(props.getProperty("mudtool.ai.max_retries",
                String.valueOf(maxRetries)));
        swcNamingRegex = props.getProperty("mudtool.naming.swc", swcNamingRegex);
        runnableNamingRegex = props.getProperty("mudtool.naming.runnable", runnableNamingRegex);
        portNamingRegex = props.getProperty("mudtool.naming.port", portNamingRegex);
        defaultExportFormat = props.getProperty("mudtool.export.format", defaultExportFormat);
        exportDirectory = props.getProperty("mudtool.export.directory", exportDirectory);
    }

    private void applyEnvironment() {
        String host = System.getenv("MUD_HOST");
        if (host != null) sidecarHost = host;

        String port = System.getenv("MUD_PORT");
        if (port != null) sidecarPort = Integer.parseInt(port);

        String python = System.getenv("MUD_PYTHON_PATH");
        if (python != null) pythonPath = python;

        String backend = System.getenv("MUD_AI_BACKEND");
        if (backend != null) aiBackend = backend;
    }

    public String getSidecarUrl() {
        return String.format("http://%s:%d/api/v1", sidecarHost, sidecarPort);
    }

    // ── Getters ────────────────────────────────────

    public String getSidecarHost() { return sidecarHost; }
    public int getSidecarPort() { return sidecarPort; }
    public boolean isAutoStartSidecar() { return autoStartSidecar; }
    public String getPythonPath() { return pythonPath; }
    public String getSidecarWorkDir() { return sidecarWorkDir; }
    public int getConnectionTimeoutMs() { return connectionTimeoutMs; }
    public int getReadTimeoutMs() { return readTimeoutMs; }
    public String getAiBackend() { return aiBackend; }
    public double getConfidenceThreshold() { return confidenceThreshold; }
    public int getMaxRetries() { return maxRetries; }
    public String getSwcNamingRegex() { return swcNamingRegex; }
    public String getRunnableNamingRegex() { return runnableNamingRegex; }
    public String getPortNamingRegex() { return portNamingRegex; }
    public String getDefaultExportFormat() { return defaultExportFormat; }
    public String getExportDirectory() { return exportDirectory; }

    // ── Setters ────────────────────────────────────

    public void setSidecarHost(String host) { this.sidecarHost = host; }
    public void setSidecarPort(int port) { this.sidecarPort = port; }
    public void setAutoStartSidecar(boolean auto) { this.autoStartSidecar = auto; }
    public void setPythonPath(String path) { this.pythonPath = path; }
    public void setSidecarWorkDir(String dir) { this.sidecarWorkDir = dir; }
    public void setAiBackend(String backend) { this.aiBackend = backend; }
    public void setConfidenceThreshold(double threshold) { this.confidenceThreshold = threshold; }
}
