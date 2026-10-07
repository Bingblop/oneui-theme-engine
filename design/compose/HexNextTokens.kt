// Generated from design/tokens.json by design/build_tokens.py. Do not edit by hand.
package com.hexnext.themer.ui.theme

import androidx.compose.material3.darkColorScheme
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

object HexColors {
    val bgBase = Color(0xFF080A0F)
    val bgSurface = Color(0xFF10141E)
    val bgCard = Color(0xBF161C2A)
    val bgCardHover = Color(0xF21E263A)
    val scrim = Color(0xE6080A0F)
    val borderGlass = Color(0x17FFFFFF)
    val borderActive = Color(0x9900E5FF)
    val accent = Color(0xFF00E5FF)
    val accentGlow = Color(0x5900E5FF)
    val secondary = Color(0xFF7C4DFF)
    val onAccent = Color(0xFF000000)
    val textMain = Color(0xFFFFFFFF)
    val textMuted = Color(0xFF8E9BAE)
    val textDim = Color(0xFF546075)
    val success = Color(0xFF00E676)
    val warning = Color(0xFFFFD600)
    val danger = Color(0xFFFF5252)
}

object HexRadius {
    val sm = 8.dp
    val md = 14.dp
    val lg = 20.dp
    val xl = 28.dp
    val phone = 36.dp
    val pill = 999.dp
}

object HexSpace {
    val s1 = 4.dp
    val s2 = 8.dp
    val s3 = 12.dp
    val s4 = 16.dp
    val s5 = 24.dp
    val s6 = 32.dp
}

object HexBlur {
    val glass = 20.dp
    val card = 12.dp
}

object HexElevation {
    val glowY = 4.dp
    val glowBlur = 14.dp
    val glowColor = Color(0x5900E5FF)
    val floatY = 20.dp
    val floatBlur = 50.dp
    val floatColor = Color(0xCC000000)
}

/** Sections and captions are uppercase: apply `.uppercase()` to the text. */
object HexType {
    val display = TextStyle(fontSize = 28.sp, fontWeight = FontWeight.W800, letterSpacing = -0.5.sp)
    val brand = TextStyle(fontSize = 20.sp, fontWeight = FontWeight.W800, letterSpacing = -0.5.sp)
    val section = TextStyle(fontSize = 14.sp, fontWeight = FontWeight.W800, letterSpacing = 0.6.sp)
    val body = TextStyle(fontSize = 14.sp, fontWeight = FontWeight.W600, letterSpacing = 0.sp)
    val control = TextStyle(fontSize = 13.sp, fontWeight = FontWeight.W700, letterSpacing = 0.sp)
    val caption = TextStyle(fontSize = 11.sp, fontWeight = FontWeight.W700, letterSpacing = 0.5.sp)
}

val HexNextColorScheme = darkColorScheme(
    primary = HexColors.accent,
    onPrimary = HexColors.onAccent,
    secondary = HexColors.secondary,
    onSecondary = HexColors.textMain,
    background = HexColors.bgBase,
    onBackground = HexColors.textMain,
    surface = HexColors.bgSurface,
    onSurface = HexColors.textMain,
    surfaceVariant = HexColors.bgCard,
    onSurfaceVariant = HexColors.textMuted,
    outline = HexColors.borderGlass,
    error = HexColors.danger,
    onError = HexColors.onAccent,
)
