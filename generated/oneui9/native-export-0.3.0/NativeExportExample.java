import android.content.res.AssetManager;
import java.nio.file.Paths;
import java.io.FileOutputStream;
import org.bingblop.oneui.studio.ThemeSource;

class NativeExportExample {
    public static void main(String[] args) throws Exception {
        ThemeSource source = ThemeSource.builtin(new AssetManager(Paths.get(args[0])), "sources/neon-violet.ouitheme");
        source.setColor(true, "background", "#FF030712");
        source.setColor(true, "accent", "#FF22D3EE");
        source.setColor(true, "onAccent", "#FF001F25");
        source.setColor(false, "background", "#FFF8FAFC");
        source.setColor(false, "accent", "#FF0E7490");
        source.setColor(false, "onAccent", "#FFFFFFFF");
        source.setOverrideColor(true, "systemui", "quickPanelBackground", "#F0111828");
        source.setOverrideColor(false, "systemui", "quickPanelBackground", "#F0E8F3F8");
        source.setOverrideColor(true, "settings", "settingsIcon", "#FF22D3EE");
        source.setOverrideColor(false, "settings", "settingsIcon", "#FF0E7490");
        source.setDimension(true, "cornerRadius", 20, "dp");
        source.setDimension(false, "cornerRadius", 16, "dp");
        try (FileOutputStream output = new FileOutputStream(args[1])) { source.exportTo(output); }
    }
}
