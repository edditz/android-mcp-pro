plugins {
    java
    application
    id("com.github.johnrengelman.shadow") version "8.1.1"
}

repositories {
    google()
    mavenCentral()
}

dependencies {
    implementation("com.android.tools.ddms:ddmlib:30.4.0")
    testImplementation("org.junit.jupiter:junit-jupiter:5.10.2")
}

java {
    toolchain { languageVersion.set(JavaLanguageVersion.of(17)) }
}

application {
    mainClass.set("com.androidmcp.inspector.Main")
}

tasks.test { useJUnitPlatform() }

tasks.shadowJar {
    archiveBaseName.set("deep-inspector")
    archiveClassifier.set("")
    archiveVersion.set("")
    // Publish the fat-jar straight into the repo's prebuilt/ dir — the path the Python
    // runtime loads (see _DEFAULT_JAR in src/android_mcp/__main__.py). This removes the
    // separate "copy into prebuilt/" step: `./gradlew shadowJar` alone keeps the runtime
    // jar current, so a Java change can never silently run against a stale artifact.
    destinationDirectory.set(file("$rootDir/../prebuilt"))
}
