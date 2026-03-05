# NeoMAGI

[English](README.md) | [中文](README_ch.md)

NeoMAGI ist ein Open-Source-Projekt fuer einen personal agent.

Die Produktidee ist einfach: ein Agent, der ueber laengere Zeit nuetzliche Erinnerung behalten kann, die Informationsinteressen des Nutzers vertritt und sich schrittweise von gehosteten Modell-APIs zu lokaleren und besser kontrollierbaren Modell-Stacks bewegen kann.

## Produktpositionierung

NeoMAGI soll keine generische Chatbot-Huelle sein.

Die angestrebte Richtung ist eine langfristige partnerartige AI mit folgenden Eigenschaften:
- nuetzlichen Kontext ueber Zeit behalten
- im Interesse des Nutzers handeln statt im Interesse einer Plattform
- Faehigkeiten kontrolliert und auditierbar erweitern
- einen realistischen Migrationspfad von kommerziellen APIs zu lokalen Modellen offenhalten

## Prinzipien

- Gruendlich denken, einfach umsetzen.
- Zuerst den kleinsten brauchbaren geschlossenen Kreislauf bauen.
- Unnoetige Abstraktion und Abhaengigkeiten vermeiden.
- Governance, Rollback und Scope-Grenzen als Produktmerkmale behandeln, nicht nur als Engineering-Details.

## Aktueller Stand

Dieses Repository befindet sich noch in einer fruehen Produktaufbauphase.

Das Phase-1-Fundament ist weitgehend aufgebaut und als Referenz archiviert. In Phase 2 geht es darum, die Last alter Kontexte zu reduzieren, das naechste Produktkapitel klarer zu machen und sich von Basisinfrastruktur in Richtung eines expliziteren Modells fuer Wachstum und Faehigkeitsentwicklung zu bewegen.

Diese README bleibt bewusst auf hoher Ebene. Sie ist als Projekteinfuehrung gedacht, nicht als vollstaendlicher Implementierungsvertrag.

## Dokumentation

- Einstieg in die Design-Dokumente: `design_docs/index.md`
- Phase-1-Archiv: `design_docs/phase1/index.md`
- Laufzeit-Prompt-Modell: `design_docs/system_prompt.md`
- Memory-Prinzipien: `design_docs/memory_architecture_v2.md`
- Repository-Governance: `AGENTS.md`, `CLAUDE.md`, `AGENTTEAMS.md`

## Hinweis

Das Projekt entwickelt sich aktiv weiter.

Namen, Grenzen und Implementierungsdetails koennen sich weiter aendern, waehrend die Produktrichtung schaerfer wird und mehr Systemteile durch echte Nutzung validiert werden.
