package dev.mcflow.client;

import com.mojang.blaze3d.pipeline.RenderTarget;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.screens.Screen;

/** Every Minecraft API that differs between supported versions, and nothing else. */
final class Compat {
    private Compat() {}

    static Screen currentScreen(Minecraft mc) {
        //? if >=26.1 {
        return mc.gui.screen();
        //?} else {
        /*return mc.screen;
        *///?}
    }

    static void setScreen(Minecraft mc, Screen screen) {
        //? if >=26.1 {
        mc.gui.setScreen(screen);
        //?} else {
        /*mc.setScreen(screen);
        *///?}
    }

    static RenderTarget mainRenderTarget(Minecraft mc) {
        //? if >=26.1 {
        return mc.gameRenderer.mainRenderTarget();
        //?} else {
        /*return mc.getMainRenderTarget();
        *///?}
    }
}
