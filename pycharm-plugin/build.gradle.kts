/**
 * Aura Code Intelligence PyCharm Plugin - Gradle Build Configuration
 *
 * ADR-048 Phase 3: PyCharm Plugin
 */

plugins {
    id("java")
    id("org.jetbrains.kotlin.jvm") version "1.9.21"
    id("org.jetbrains.intellij") version "1.17.4"
}

group = "com.aenealabs"
version = "2.0.0"

repositories {
    mavenCentral()
}

// Java toolchain -- declarative + portable. Gradle auto-provisions JDK 17 if
// the local one differs. Replaces the prior hardcoded `org.gradle.java.home`
// in gradle.properties (was an Apple Silicon Homebrew path; broke CI runners
// and any non-Mac dev). Surfaced by CodeQL Java autobuild failure 2026-04-02.
java {
    toolchain {
        languageVersion.set(JavaLanguageVersion.of(17))
    }
}

dependencies {
    implementation("com.google.code.gson:gson:2.10.1")
}

// Configure Gradle IntelliJ Plugin
intellij {
    version.set("2023.2.5")
    type.set("PC") // PyCharm Professional
    plugins.set(listOf("PythonCore"))  // Use bundled Python plugin ID
}

tasks {
    // Set the JVM compatibility versions
    withType<JavaCompile> {
        sourceCompatibility = "17"
        targetCompatibility = "17"
    }

    withType<org.jetbrains.kotlin.gradle.tasks.KotlinCompile> {
        kotlinOptions.jvmTarget = "17"
    }

    patchPluginXml {
        sinceBuild.set("232")
        untilBuild.set("251.*")
    }

    signPlugin {
        certificateChain.set(System.getenv("CERTIFICATE_CHAIN"))
        privateKey.set(System.getenv("PRIVATE_KEY"))
        password.set(System.getenv("PRIVATE_KEY_PASSWORD"))
    }

    publishPlugin {
        token.set(System.getenv("PUBLISH_TOKEN"))
    }

    buildSearchableOptions {
        enabled = false
    }
}
