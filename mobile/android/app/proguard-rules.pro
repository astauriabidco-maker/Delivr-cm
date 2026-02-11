# =============================================
# DELIVR-CM ProGuard Rules
# =============================================

# Flutter wrapper
-keep class io.flutter.app.** { *; }
-keep class io.flutter.plugin.**  { *; }
-keep class io.flutter.util.**  { *; }
-keep class io.flutter.view.**  { *; }
-keep class io.flutter.**  { *; }
-keep class io.flutter.plugins.**  { *; }

# Dio/OkHttp
-dontwarn okhttp3.**
-dontwarn okio.**
-dontwarn javax.annotation.**

# Geolocator
-keep class com.baseflow.geolocator.** { *; }

# Web Socket Channel
-keep class io.flutter.plugins.webviewflutter.** { *; }

# Keep annotations
-keepattributes *Annotation*
-keepattributes Signature
-keepattributes RuntimeVisibleAnnotations
