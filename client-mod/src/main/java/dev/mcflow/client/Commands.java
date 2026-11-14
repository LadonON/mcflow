package dev.mcflow.client;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Set;
import java.util.concurrent.CompletableFuture;
import java.util.function.Supplier;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;
import net.minecraft.client.gui.components.AbstractWidget;
import net.minecraft.client.gui.components.events.GuiEventListener;
import net.minecraft.client.gui.screens.ConnectScreen;
import net.minecraft.client.gui.screens.PauseScreen;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.gui.screens.inventory.AbstractContainerScreen;
import net.minecraft.client.gui.screens.inventory.InventoryScreen;
import net.minecraft.client.multiplayer.ServerData;
import net.minecraft.client.multiplayer.resolver.ServerAddress;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.world.inventory.Slot;
import net.minecraft.world.item.ItemStack;

/**
 * What mcflow-server can ask the client to do. Everything touching the game runs on Minecraft's client thread.
 *
 * <p>Safety: the client only connects to servers on this computer, and every command that acts in the game or
 * reads the screen refuses to run unless the client is connected to such a server.
 */
final class Commands {
    private static final Set<String> LOOPBACK = Set.of("127.0.0.1", "localhost", "::1", "[::1]");

    private final Minecraft mc;
    private final String minecraftVersion;

    Commands(Minecraft mc, String minecraftVersion) {
        this.mc = mc;
        this.minecraftVersion = minecraftVersion;
    }

    CompletableFuture<JsonElement> run(String command, JsonObject args) {
        return switch (command) {
            case "status" -> onClientThread(this::status);
            case "connect" -> onClientThread(() -> connect(args));
            case "chat" -> onClientThread(() -> chat(args));
            case "command" -> onClientThread(() -> command(args));
            case "open_inventory" -> onClientThread(this::openInventory);
            case "close_screen" -> onClientThread(this::closeScreen);
            case "screen" -> onClientThread(this::screen);
            case "screenshot" -> mc.submit(() -> screenshot(args)).thenCompose(f -> f);
            case "quit" -> onClientThread(() -> {
                mc.stop();
                return JsonNull.INSTANCE;
            });
            default -> CompletableFuture.failedFuture(new CommandException("unknown command: " + command));
        };
    }

    private CompletableFuture<JsonElement> onClientThread(Supplier<JsonElement> action) {
        return mc.submit(action);
    }

    private static boolean isLoopback(String host) {
        return LOOPBACK.contains(host.toLowerCase());
    }

    private String connectedHost() {
        ServerData server = mc.getCurrentServer();
        return server == null ? null : ServerAddress.parseString(server.ip).getHost();
    }

    private void requireLocalServer() {
        String host = connectedHost();
        if (mc.player == null || host == null) {
            throw new CommandException("not connected to a server; use connect first");
        }
        if (!isLoopback(host)) {
            throw new CommandException("connected to " + host + ", which isn't on this computer; mcflow only controls "
                    + "the client on local test servers");
        }
        // The user is usually in another window while mcflow drives the game, so a pause menu may be open.
        if (Compat.currentScreen(mc) instanceof PauseScreen) {
            Compat.setScreen(mc, null);
        }
    }

    private JsonElement status() {
        JsonObject s = new JsonObject();
        s.addProperty("minecraft", minecraftVersion);
        s.addProperty("inWorld", mc.player != null && mc.level != null);
        ServerData server = mc.getCurrentServer();
        s.addProperty("server", server == null ? null : server.ip);
        s.addProperty("player", mc.player == null ? null : mc.player.getScoreboardName());
        Screen screen = Compat.currentScreen(mc);
        s.addProperty("screen", screen == null ? null : screen.getClass().getSimpleName());
        s.addProperty("screenTitle", screen == null ? null : screen.getTitle().getString());
        s.addProperty("windowWidth", mc.getWindow().getWidth());
        s.addProperty("windowHeight", mc.getWindow().getHeight());
        return s;
    }

    private JsonElement connect(JsonObject args) {
        String address = args.get("address").getAsString();
        ServerAddress parsed = ServerAddress.parseString(address);
        if (!isLoopback(parsed.getHost())) {
            throw new CommandException(parsed.getHost() + " isn't on this computer; mcflow only joins local test servers");
        }
        if (mc.player != null) {
            String host = connectedHost();
            if (host != null && mc.getCurrentServer().ip.equals(address)) {
                JsonObject already = new JsonObject();
                already.addProperty("alreadyConnected", true);
                return already;
            }
            throw new CommandException("already in a world; quit to the title screen before joining another server");
        }
        // Without this the game pauses whenever its window loses focus, which is most of the time while mcflow
        // drives it. The setting lives in mcflow's own game folder, so the user's other installs keep theirs.
        if (mc.options.pauseOnLostFocus) {
            mc.options.pauseOnLostFocus = false;
            mc.options.save();
        }
        ServerData data = new ServerData("mcflow test server", address, ServerData.Type.OTHER);
        // Accept the server's resource pack without the prompt. Only ever applied to local servers (checked above).
        data.setResourcePackStatus(ServerData.ServerPackStatus.ENABLED);
        ConnectScreen.startConnecting(Compat.currentScreen(mc), mc, parsed, data, false, null);
        JsonObject started = new JsonObject();
        started.addProperty("connecting", address);
        return started;
    }

    private JsonElement chat(JsonObject args) {
        requireLocalServer();
        mc.player.connection.sendChat(args.get("message").getAsString());
        return JsonNull.INSTANCE;
    }

    private JsonElement command(JsonObject args) {
        requireLocalServer();
        String command = args.get("command").getAsString();
        mc.player.connection.sendCommand(command.startsWith("/") ? command.substring(1) : command);
        return JsonNull.INSTANCE;
    }

    private JsonElement openInventory() {
        requireLocalServer();
        Compat.setScreen(mc, new InventoryScreen(mc.player));
        return screen();
    }

    private JsonElement closeScreen() {
        requireLocalServer();
        if (Compat.currentScreen(mc) instanceof AbstractContainerScreen<?>) {
            mc.player.clientSideCloseContainer();
        } else {
            Compat.setScreen(mc, null);
        }
        return JsonNull.INSTANCE;
    }

    private JsonElement screen() {
        requireLocalServer();
        Screen screen = Compat.currentScreen(mc);
        JsonObject out = new JsonObject();
        if (screen == null) {
            out.add("screen", JsonNull.INSTANCE);
            return out;
        }
        out.addProperty("screen", screen.getClass().getSimpleName());
        out.addProperty("title", screen.getTitle().getString());

        JsonArray widgets = new JsonArray();
        for (GuiEventListener child : screen.children()) {
            if (!(child instanceof AbstractWidget w)) continue;
            JsonObject o = new JsonObject();
            o.addProperty("type", w.getClass().getSimpleName());
            o.addProperty("text", w.getMessage().getString());
            o.addProperty("x", w.getX());
            o.addProperty("y", w.getY());
            o.addProperty("width", w.getWidth());
            o.addProperty("height", w.getHeight());
            o.addProperty("active", w.isActive());
            o.addProperty("visible", w.visible);
            widgets.add(o);
        }
        out.add("widgets", widgets);

        if (screen instanceof AbstractContainerScreen<?> container) {
            JsonArray slots = new JsonArray();
            for (Slot slot : container.getMenu().slots) {
                ItemStack stack = slot.getItem();
                if (stack.isEmpty()) continue;
                JsonObject o = new JsonObject();
                o.addProperty("slot", slot.index);
                o.addProperty("item", BuiltInRegistries.ITEM.getKey(stack.getItem()).toString());
                o.addProperty("count", stack.getCount());
                o.addProperty("name", stack.getHoverName().getString());
                slots.add(o);
            }
            out.add("slots", slots);
        }
        return out;
    }

    private CompletableFuture<JsonElement> screenshot(JsonObject args) {
        requireLocalServer();
        Path path = Path.of(args.get("path").getAsString());
        if (!path.isAbsolute() || !path.getFileName().toString().toLowerCase().endsWith(".png")) {
            throw new CommandException("screenshot path must be an absolute path ending in .png");
        }
        CompletableFuture<JsonElement> done = new CompletableFuture<>();
        Screenshot.takeScreenshot(Compat.mainRenderTarget(mc), image -> {
            try (image) {
                Files.createDirectories(path.getParent());
                image.writeToFile(path);
                JsonObject o = new JsonObject();
                o.addProperty("path", path.toString());
                o.addProperty("width", image.getWidth());
                o.addProperty("height", image.getHeight());
                done.complete(o);
            } catch (Exception e) {
                done.completeExceptionally(new CommandException("couldn't save screenshot: " + e.getMessage()));
            }
        });
        return done;
    }
}
