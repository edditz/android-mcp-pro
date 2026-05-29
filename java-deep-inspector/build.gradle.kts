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
}
