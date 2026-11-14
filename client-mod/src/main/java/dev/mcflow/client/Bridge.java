package dev.mcflow.client;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.io.Writer;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.nio.file.FileSystems;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.PosixFilePermissions;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.HexFormat;
import java.util.concurrent.TimeUnit;

/**
 * Loopback-only control channel for mcflow-server. One JSON object per line in each direction.
 *
 * <p>Request: {"token": "...", "id": 1, "command": "status", "args": {...}}
 * Reply:   {"id": 1, "ok": true, "result": ...} or {"id": 1, "ok": false, "error": "..."}
 *
 * <p>The port and a random token are written to {@code <game dir>/mcflow/bridge.json}, readable only by the
 * user who runs the game, and deleted when the game exits.
 */
final class Bridge {
    // Keep null fields: mcflow-server reads "screen": null as "no screen open".
    private static final Gson GSON = new GsonBuilder().serializeNulls().create();
    private static final long COMMAND_TIMEOUT_SECONDS = 30;

    private final ServerSocket socket;
    private final byte[] token;
    private final Commands commands;
    private final Path file;

    private Bridge(ServerSocket socket, String token, Commands commands, Path file) {
        this.socket = socket;
        this.token = token.getBytes(StandardCharsets.UTF_8);
        this.commands = commands;
        this.file = file;
    }

    static Bridge start(Path gameDir, Commands commands, String minecraftVersion, String modVersion)
            throws IOException {
        ServerSocket socket = new ServerSocket(0, 4, InetAddress.getLoopbackAddress());
        byte[] random = new byte[32];
        new SecureRandom().nextBytes(random);
        String token = HexFormat.of().formatHex(random);

        JsonObject info = new JsonObject();
        info.addProperty("port", socket.getLocalPort());
        info.addProperty("token", token);
        info.addProperty("pid", ProcessHandle.current().pid());
        info.addProperty("minecraft", minecraftVersion);
        info.addProperty("mod", modVersion);
        Path file = writePrivately(gameDir.resolve("mcflow").resolve("bridge.json"), GSON.toJson(info));

        Bridge bridge = new Bridge(socket, token, commands, file);
        Thread acceptor = new Thread(bridge::acceptLoop, "mcflow-bridge");
        acceptor.setDaemon(true);
        acceptor.start();
        Runtime.getRuntime().addShutdownHook(new Thread(bridge::close, "mcflow-bridge-cleanup"));
        return bridge;
    }

    private static Path writePrivately(Path file, String content) throws IOException {
        Files.createDirectories(file.getParent());
        Files.deleteIfExists(file);
        if (FileSystems.getDefault().supportedFileAttributeViews().contains("posix")) {
            Files.createFile(file, PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rw-------")));
        }
        Files.writeString(file, content, StandardCharsets.UTF_8);
        return file;
    }

    int port() {
        return socket.getLocalPort();
    }

    private void acceptLoop() {
        while (!socket.isClosed()) {
            try {
                Socket client = socket.accept();
                Thread handler = new Thread(() -> serve(client), "mcflow-bridge-client");
                handler.setDaemon(true);
                handler.start();
            } catch (IOException e) {
                if (!socket.isClosed()) McflowClient.LOG.warn("mcflow bridge: accept failed", e);
            }
        }
    }

    private void serve(Socket client) {
        try (client;
             BufferedReader in = new BufferedReader(new InputStreamReader(client.getInputStream(), StandardCharsets.UTF_8));
             Writer out = new OutputStreamWriter(client.getOutputStream(), StandardCharsets.UTF_8)) {
            String line;
            while ((line = in.readLine()) != null) {
                out.write(GSON.toJson(handle(line)));
                out.write('\n');
                out.flush();
            }
        } catch (IOException e) {
            // The other side hung up; nothing to clean up beyond the socket.
        }
    }

    private JsonObject handle(String line) {
        JsonObject reply = new JsonObject();
        try {
            JsonObject request = JsonParser.parseString(line).getAsJsonObject();
            if (request.has("id")) reply.add("id", request.get("id"));
            String given = request.has("token") ? request.get("token").getAsString() : "";
            if (!MessageDigest.isEqual(given.getBytes(StandardCharsets.UTF_8), token)) {
                return fail(reply, "bad token");
            }
            String command = request.get("command").getAsString();
            JsonObject args = request.has("args") ? request.getAsJsonObject("args") : new JsonObject();
            JsonElement result = commands.run(command, args).get(COMMAND_TIMEOUT_SECONDS, TimeUnit.SECONDS);
            reply.addProperty("ok", true);
            reply.add("result", result);
            return reply;
        } catch (Exception e) {
            Throwable cause = e.getCause() != null && !(e instanceof CommandException) ? e.getCause() : e;
            return fail(reply, cause.getMessage() == null ? cause.toString() : cause.getMessage());
        }
    }

    private static JsonObject fail(JsonObject reply, String message) {
        reply.addProperty("ok", false);
        reply.addProperty("error", message);
        return reply;
    }

    void close() {
        try {
            socket.close();
            Files.deleteIfExists(file);
        } catch (IOException ignored) {
            // Shutting down anyway.
        }
    }
}
