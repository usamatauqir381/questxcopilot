# Quick Reference - CSS Variables & Customization

## CSS Variables (in :root)

```css
/* Primary Colors */
--primary-dark: #0f1419;           /* Main background */
--primary-darker: #0a0e13;         /* Darker background */
--accent-cyan: #00d9ff;            /* Primary highlight */
--accent-purple: #bb86fc;          /* Secondary highlight */
--accent-blue: #1f88ff;            /* Interactive color */
--accent-green: #00e676;           /* Success state */

/* Neutral Colors */
--text-primary: #ffffff;           /* Main text */
--text-secondary: #b3b3b3;         /* Secondary text */
--text-muted: #888888;             /* Muted/disabled text */
--surface-dark: #1a1f28;           /* Card backgrounds */
--surface-light: #252d38;          /* Light surfaces */
--border-color: #333d4d;           /* Borders */

/* Semantic */
--error: #ff5252;                  /* Error state */
--warning: #ffb74d;                /* Warning state */
--success: #4caf50;                /* Success state */

/* Gradients */
--gradient-primary: linear-gradient(135deg, #1f88ff 0%, #bb86fc 100%);
--gradient-accent: linear-gradient(135deg, #00d9ff 0%, #1f88ff 100%);
--gradient-hover: linear-gradient(135deg, #bb86fc 0%, #00d9ff 100%);
```

---

## Common CSS Snippets

### Change Primary Color
```css
:root {
  --accent-cyan: #FF6B6B;           /* Your new color */
  --gradient-primary: linear-gradient(135deg, #1f88ff 0%, #FF6B6B 100%);
  --gradient-hover: linear-gradient(135deg, #FF6B6B 0%, #00d9ff 100%);
}
```

### Add Light Theme
```css
body.light-theme {
  --primary-dark: #ffffff;
  --primary-darker: #f5f5f5;
  --text-primary: #0f1419;
  --text-secondary: #666666;
  --text-muted: #999999;
  --surface-dark: #f0f0f0;
  --surface-light: #e8e8e8;
  --border-color: #ddd;
}
```

### Add Custom Animation
```css
@keyframes slideUp {
  from { transform: translateY(50px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

.my-element {
  animation: slideUp 0.6s ease-out;
}
```

### Adjust Button Size
```css
button.primary {
  padding: 1.2rem 2rem;             /* Change from 0.95rem 1.5rem */
  font-size: 1.1rem;                /* Change from 1rem */
}
```

### Change Focus Color
```css
input:focus {
  border-color: #FF6B6B;            /* Change from cyan */
  box-shadow: 0 0 0 3px rgba(255, 107, 107, 0.15);
}
```

---

## Layout Classes

```html
<!-- Main Container -->
<main class="container">
  <!-- Automatically centered, dark background, bordered -->
</main>

<!-- Form Group -->
<fieldset>
  <legend>Section Title</legend>
  <!-- Multiple labels and inputs -->
</fieldset>

<!-- Question Sections -->
<section class="question hidden">
  <!-- Hidden by default, shown with JavaScript -->
</section>

<!-- Button Group -->
<div class="controls">
  <button>Button 1</button>
  <button>Button 2</button>
</div>

<!-- Helper Text -->
<p class="muted">Secondary information</p>

<!-- Instructions Block -->
<div class="instructions">
  <!-- Highlighted instructions with cyan border -->
</div>
```

---

## Responsive Breakpoints

```css
/* Mobile First Approach */
/* Default: 320px - 640px */

@media (max-width: 768px) {
  /* Tablets and below */
}

@media (max-width: 900px) {
  /* Medium devices */
}

/* Desktop: 900px+ (all effects enabled) */
```

---

## Animation Reference

### Available Animations

| Name | Duration | Effect |
|------|----------|--------|
| fadeInDown | 0.8s | Header entrance from top |
| fadeInUp | 0.6s | Content entrance from bottom |
| slideIn | 0.3s | Side transition |
| glow | 1s infinite | Pulsing glow effect |
| pulse | 2s infinite | Breathing effect |
| bounce | 0.6s | Success popup |

### Apply Animation
```css
.my-element {
  animation: fadeInUp 0.6s ease-out;
}

.my-element.delayed {
  animation: fadeInUp 0.6s ease-out 0.3s backwards;
  /* 0.3s delay before animation starts */
}
```

---

## Typical Use Cases

### Making a "Premium" Button
```html
<button type="submit" class="primary">Submit</button>
```
→ Automatically gets gradient + glow + hover effects

### Creating a Form Section
```html
<fieldset>
  <legend>Your Title</legend>
  <label>Field Name <input type="text"></label>
</fieldset>
```
→ Gets dark background with cyan legend

### Highlighting Important Text
```html
<p class="instructions">Important information</p>
```
→ Gets cyan border and background tint

### Hidden Content (revealed by JS)
```html
<section class="question hidden"></section>
```
→ CSS: `display: none`, triggered by JavaScript

---

## Typography Classes

```html
<!-- Large Heading (auto-gradient) -->
<h1>Page Title</h1>

<!-- Question/Section Heading -->
<h3>Question 1</h3>

<!-- Normal Paragraph -->
<p>Regular text appears here</p>

<!-- Secondary/Muted Text -->
<p class="muted">Smaller, less emphasized text</p>
```

---

## Color Usage Guide

### When to Use Each Color

| Color | Usage | Example |
|-------|-------|---------|
| **Cyan** | Focus, highlights, primary CTAs | Button focus, active states |
| **Purple** | Secondary action, gradient | Button hover, accents |
| **Blue** | Interactive elements | Links, primary buttons |
| **Green** | Success, positive feedback | Success page, checkmarks |
| **Red** | Errors, warnings, blocked | Error states, blocked page |
| **Orange** | Warnings, timers | Warning text, timer alerts |

---

## Box Shadow Reference

### Subtle (Cards)
```css
box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
```

### Glow (Hover)
```css
box-shadow: 0 0 30px rgba(187, 134, 252, 0.5);
```

### Inset (Depth)
```css
box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.1);
```

---

## Backdrop Filter

```css
/* Frosted glass effect */
backdrop-filter: blur(10px);

/* Note: Not supported in Firefox - will be ignored gracefully */
```

---

## Focus States

### For Inputs
```css
input:focus {
  outline: none;
  border-color: var(--accent-cyan);
  background: rgba(0, 217, 255, 0.08);
  box-shadow: 0 0 0 3px rgba(0, 217, 255, 0.15);
}
```

### For Buttons
```css
button:focus {
  outline: 2px solid var(--accent-cyan);
  outline-offset: 2px;
}
```

---

## Transition Timing

Standard timing functions used:
- **ease-out** (0.3s) - Used for exits and hover states
- **ease-in-out** (0.6s) - Used for animations
- **ease** (default) - General purpose

```css
transition: all 0.3s ease;        /* Safe default */
transition: transform 0.3s ease-out;  /* For transforms */
animation: fadeInUp 0.6s ease-out;    /* For keyframes */
```

---

## Accessibility Tweaks

### Respect Prefers-Reduced-Motion
```css
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

### High Contrast Mode
Add to your CSS:
```css
@media (prefers-contrast: more) {
  :root {
    --text-primary: #ffffff;
    --accent-cyan: #00ffff;
    --border-color: #00ffff;
  }
}
```

---

## Testing Checklist

- [ ] Colors are visible (check contrast with WebAIM tool)
- [ ] Focus states are visible
- [ ] Animations don't break with reduced-motion
- [ ] Responsive at 320px, 768px, 1200px
- [ ] Works in Chrome, Firefox, Safari
- [ ] Keyboard navigation works
- [ ] Touch targets are ≥18px
- [ ] No layout shift on hover
- [ ] Smooth 60fps animations

---

## Common Issues & Solutions

### Buttons not showing gradient
```css
/* Wrong */
background: var(--primary-dark);

/* Right */
background: var(--gradient-primary);
```

### Focus ring not showing
```css
/* Add this */
input:focus {
  outline: 2px solid var(--accent-cyan);
  outline-offset: 2px;
}
```

### Animation jittery
```css
/* Add GPU acceleration */
will-change: transform;
transform: translateZ(0);
```

### Text hard to read
```css
/* Increase contrast */
color: var(--text-primary);      /* Use primary, not secondary */
background: var(--surface-dark); /* Darker background */
```

---

## Resources

- **CSS Variables**: https://developer.mozilla.org/en-US/docs/Web/CSS/--*
- **Animations**: https://developer.mozilla.org/en-US/docs/Web/CSS/animation
- **Backdrop Filter**: https://developer.mozilla.org/en-US/docs/Web/CSS/backdrop-filter
- **Gradients**: https://developer.mozilla.org/en-US/docs/Web/CSS/linear-gradient()
- **Media Queries**: https://developer.mozilla.org/en-US/docs/Web/CSS/Media_Queries
- **Accessibility**: https://www.w3.org/WAI/WCAG21/quickref/

---

## Need Help?

1. **Check DESIGN.md** - For complete design system
2. **Check STYLE_GUIDE.md** - For detailed component docs
3. **Check VISUAL_COMPARISON.md** - For before/after examples
4. **Check source CSS** - Organized with clear comments
5. **Test with browser DevTools** - Use Elements/Inspector

---

**Quick Reference Version**: 1.0  
**Last Updated**: December 2, 2025
