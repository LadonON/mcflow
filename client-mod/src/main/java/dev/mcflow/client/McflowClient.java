package dev.mcflow.client;

import java.io.IOException;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.loader.api.FabricLoader;
import net.minecraft.client.Minecraft;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public final class McflowClient implements ClientModInitializer {
    static final Logger LOG = LoggerFactory.getLogger("mcflow");

    @Override
    public void onInitializeClient() {
        FabricLoader loader = FabricLoader.getInstance();
        String minecraft = version(loader, "minecraft");
        try {
            Bridge bridge = Bridge.start(loader.getGameDir(), new Commands(Minecraft.getInstance(), minecraft),
                    minecraft, version(loader, "mcflow"));
            LOG.info("mcflow bridge listening on 127.0.0.1:{}", bridge.port());
        } catch (IOException e) {
            LOG.error("mcflow bridge couldn't start; mcflow can't control this client", e);
        }
    }

    private static String version(FabricLoader loader, String modId) {
        return loader.getModContainer(modId)
                .map(c -> c.getMetadata().getVersion().getFriendlyString())
                .orElse("unknown");
    }
}
