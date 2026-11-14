package dev.mcflow.client;

import com.mojang.blaze3d.platform.NativeImage;
import java.util.function.Consumer;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.components.AbstractWidget;
import net.minecraft.client.gui.screens.ConnectScreen;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.multiplayer.ServerData;
import net.minecraft.client.multiplayer.resolver.ServerAddress;
import net.minecraft.client.Screenshot;
import net.minecraft.world.item.ItemStack;
//? if >=1.19.3 {
import net.minecraft.core.registries.BuiltInRegistries;
//?} else {
/*import net.minecraft.core.Registry;
*///?}

/**
 * Every Minecraft API that differs between supported versions, and nothing else. Version boundaries were
 * checked with javap against Loom's Mojang-named jars and are confirmed by compiling every supported version.
 */
final class Compat {
    private Compat() {}

    static Screen currentScreen(Minecraft mc) {
        //? if >=26.2 {
        return mc.gui.screen();
        //?} else {
        /*return mc.screen;
        *///?}
    }

    static void setScreen(Minecraft mc, Screen screen) {
        //? if >=26.2 {
        mc.gui.setScreen(screen);
        //?} else {
        /*mc.setScreen(screen);
        *///?}
    }

    /** Captures the last rendered frame. The callback owns the image and must close it. */
    static void takeScreenshot(Minecraft mc, Consumer<NativeImage> callback) {
        //? if >=26.2 {
        Screenshot.takeScreenshot(mc.gameRenderer.mainRenderTarget(), callback);
        //?} else if >=1.21.5 {
        /*Screenshot.takeScreenshot(mc.getMainRenderTarget(), callback);
        *///?} else if >=1.17.1 {
        /*callback.accept(Screenshot.takeScreenshot(mc.getMainRenderTarget()));
        *///?} else {
        /*callback.accept(Screenshot.takeScreenshot(mc.getWindow().getWidth(), mc.getWindow().getHeight(),
                mc.getMainRenderTarget()));
        *///?}
    }

    static void clearToasts(Minecraft mc) {
        //? if >=26.2 {
        mc.gui.toastManager().clear();
        //?} else if >=1.21.2 {
        /*mc.getToastManager().clear();
        *///?} else {
        /*mc.getToasts().clear();
        *///?}
    }

    static ServerData newServerData(String name, String address) {
        //? if >=1.20.2 {
        return new ServerData(name, address, ServerData.Type.OTHER);
        //?} else {
        /*return new ServerData(name, address, false);
        *///?}
    }

    static void startConnecting(Minecraft mc, ServerAddress address, ServerData data) {
        //? if >=1.20.5 {
        ConnectScreen.startConnecting(currentScreen(mc), mc, address, data, false, null);
        //?} else if >=1.20 {
        /*ConnectScreen.startConnecting(currentScreen(mc), mc, address, data, false);
        *///?} else {
        /*ConnectScreen.startConnecting(currentScreen(mc), mc, address, data);
        *///?}
    }

    static void sendChat(Minecraft mc, String message) {
        //? if >=1.19.3 {
        mc.player.connection.sendChat(message);
        //?} else if >=1.19.1 {
        /*mc.player.chatSigned(message, null);
        *///?} else {
        /*mc.player.chat(message);
        *///?}
    }

    /** Sends a command; {@code command} has no leading slash. */
    static void sendCommand(Minecraft mc, String command) {
        //? if >=1.19.3 {
        mc.player.connection.sendCommand(command);
        //?} else if >=1.19.1 {
        /*mc.player.commandSigned(command, null);
        *///?} else if >=1.19 {
        /*mc.player.command(command);
        *///?} else {
        /*mc.player.chat("/" + command);
        *///?}
    }

    static boolean isFullscreen(Minecraft mc) {
        //? if >=1.19 {
        return mc.options.fullscreen().get();
        //?} else {
        /*return mc.options.fullscreen;
        *///?}
    }

    /** Turns off the accessibility onboarding screen where it exists. Returns true if anything changed. */
    static boolean skipAccessibilityOnboarding(Minecraft mc) {
        //? if >=1.19.4 {
        boolean changed = mc.options.onboardAccessibility;
        mc.options.onboardAccessibility = false;
        return changed;
        //?} else {
        /*return false;
        *///?}
    }

    static int widgetX(AbstractWidget w) {
        //? if >=1.19.3 {
        return w.getX();
        //?} else {
        /*return w.x;
        *///?}
    }

    static int widgetY(AbstractWidget w) {
        //? if >=1.19.3 {
        return w.getY();
        //?} else {
        /*return w.y;
        *///?}
    }

    static String itemId(ItemStack stack) {
        //? if >=1.19.3 {
        return BuiltInRegistries.ITEM.getKey(stack.getItem()).toString();
        //?} else {
        /*return Registry.ITEM.getKey(stack.getItem()).toString();
        *///?}
    }
}
