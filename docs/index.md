---
layout: default
title: Gallery
---
<div class="hero">
  <h1>Paintings</h1>
  <p>A curated collection of paintings by ei9h7 and collaborators, spanning solo works, collaborations, and compilations.</p>
</div>

<h2 class="section-title">Individual Paintings</h2>
<div class="gallery-grid">
  {% for p in site.data.paintings %}
  <a class="gallery-card" href="{{ p.page | relative_url }}">
    <img src="{{ '/assets/images/' | append: p.image | relative_url }}" alt="{{ p.title }}" loading="lazy">
    <div class="gallery-card-body">
      <div class="gallery-card-title">{{ p.title }}</div>
      <div class="gallery-card-artist">{{ p.artist }}</div>
    </div>
  </a>
  {% endfor %}
</div>

<h2 class="section-title">Collections &amp; Compilations</h2>
<div class="gallery-grid">
  {% for c in site.data.collections %}
  <a class="gallery-card" href="{{ c.page | relative_url }}">
    <img src="{{ '/assets/images/' | append: c.image | relative_url }}" alt="{{ c.title }}" loading="lazy">
    <div class="gallery-card-body">
      <div class="gallery-card-title">{{ c.title }}</div>
      <div class="gallery-card-artist">{{ c.artist }}</div>
    </div>
  </a>
  {% endfor %}
</div>

<h2 class="section-title">Documentation</h2>
<div class="gallery-grid">
  <a class="gallery-card" href="{{ '/analysis-overview.html' | relative_url }}">
    <div class="gallery-card-body">
      <div class="gallery-card-title">Analysis Overview</div>
      <div class="gallery-card-artist">Thematic and artistic analysis of the full collection</div>
    </div>
  </a>
</div>
