import { useEffect, useRef } from "react";
import { Animated, Easing, Text, View } from "react-native";
import { palette, radius } from "@/theme";

/** Valor 0→1→0 en bucle, compartido por lupa y resplandor */
function usePulse(duration = 900) {
  const pulse = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, {
          toValue: 1,
          duration,
          easing: Easing.inOut(Easing.quad),
          useNativeDriver: true,
        }),
        Animated.timing(pulse, {
          toValue: 0,
          duration,
          easing: Easing.inOut(Easing.quad),
          useNativeDriver: true,
        }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [pulse, duration]);
  return pulse;
}

/**
 * Indicador de enriquecimiento en curso (Bloque 4): lupa que barre la
 * pizarra de lado a lado + puntos suspensivos respirando. Nada de
 * ActivityIndicator genérico — esto es "el sistema está leyendo la red
 * por ti", en el tono cálido de la marca.
 */
export function EnrichmentPulse({
  label = "Buscando más info en la red",
  compact = false,
}: {
  label?: string;
  compact?: boolean;
}) {
  const pulse = usePulse();
  const sway = pulse.interpolate({ inputRange: [0, 1], outputRange: ["-14deg", "14deg"] });
  const dip = pulse.interpolate({ inputRange: [0, 0.5, 1], outputRange: [0, -2, 0] });

  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
      <Animated.Text
        style={{
          fontSize: compact ? 13 : 16,
          transform: [{ rotate: sway }, { translateY: dip }],
        }}
      >
        🔍
      </Animated.Text>
      <Text
        style={{
          fontSize: compact ? 12 : 13,
          fontWeight: "700",
          color: palette.brandDark,
          fontStyle: "italic",
        }}
      >
        {label}
      </Text>
      <Dots />
    </View>
  );
}

/** Tres puntos que respiran en escalera, como "escribiendo…" de un chat */
function Dots() {
  const dots = [useRef(new Animated.Value(0.2)).current, useRef(new Animated.Value(0.2)).current, useRef(new Animated.Value(0.2)).current];
  useEffect(() => {
    const loops = dots.map((v, i) =>
      Animated.loop(
        Animated.sequence([
          Animated.delay(i * 180),
          Animated.timing(v, { toValue: 1, duration: 380, useNativeDriver: true }),
          Animated.timing(v, { toValue: 0.2, duration: 380, useNativeDriver: true }),
          Animated.delay((2 - i) * 180),
        ])
      )
    );
    loops.forEach((l) => l.start());
    return () => loops.forEach((l) => l.stop());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <View style={{ flexDirection: "row", gap: 2 }}>
      {dots.map((v, i) => (
        <Animated.View
          key={i}
          style={{
            width: 4,
            height: 4,
            borderRadius: 2,
            backgroundColor: palette.brandDark,
            opacity: v,
          }}
        />
      ))}
    </View>
  );
}

/**
 * Resplandor ámbar que respira sobre toda la card mientras hay trabajo en
 * segundo plano. Colocar como primer hijo de una View con overflow:"hidden".
 */
export function EnrichmentGlow() {
  const pulse = usePulse(1100);
  const glow = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.05, 0.16] });
  return (
    <Animated.View
      pointerEvents="none"
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: palette.brand,
        opacity: glow,
        borderRadius: radius.md,
      }}
    />
  );
}

/**
 * Aparición suave del contenido final cuando el enriquecimiento resuelve —
 * cambiar la `key` al cambiar de estado para relanzar el fade (sin saltos).
 */
export function FadeIn({ children, delay = 0 }: { children: React.ReactNode; delay?: number }) {
  const opacity = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    Animated.timing(opacity, {
      toValue: 1,
      duration: 450,
      delay,
      easing: Easing.out(Easing.quad),
      useNativeDriver: true,
    }).start();
  }, [opacity, delay]);
  return <Animated.View style={{ opacity }}>{children}</Animated.View>;
}
