# Test Portal - Style Guide & Development Reference

## 🎨 Design System Overview

Your test portal has been completely redesigned with a **professional, modern gaming aesthetic**. The new design features:

✨ **Dark Professional Theme** - Sophisticated dark mode with cyan/purple accents  
🎮 **Gaming Effects** - Smooth animations, gradients, and hover effects  
📱 **Fully Responsive** - Mobile, tablet, and desktop optimized  
♿ **Accessible** - WCAG AA compliant with keyboard support  
⚡ **Performance Optimized** - CSS-only animations at 60fps  

## 📐 Color System

### RGB Values (for reference)
```
Cyan (#00d9ff):        RGB(0, 217, 255)
Purple (#bb86fc):      RGB(187, 134, 252)
Blue (#1f88ff):        RGB(31, 136, 255)
Dark (#0f1419):        RGB(15, 20, 25)
Surface (#1a1f28):     RGB(26, 31, 40)
Text Primary (#fff):   RGB(255, 255, 255)
Error (#ff5252):       RGB(255, 82, 82)
```

### Key Gradients
- **Primary Button**: `linear-gradient(135deg, #1f88ff 0%, #bb86fc 100%)`
- **Hover Button**: `linear-gradient(135deg, #bb86fc 0%, #00d9ff 100%)`
- **Background**: `linear-gradient(135deg, #0f1419 0%, #0a0e13 100%)`

## 🎯 Component Usage

### Buttons
```html
<!-- Primary Button -->
<button type="submit" class="primary">Send Code</button>

<!-- Link Button -->
<a href="/download" class="primary">Download</a>
```

Effects:
- Hover: Purple-cyan gradient, 30px glow, -2px translation
- Active: Returns to normal position
- Focus: Cyan outline

### Form Inputs
```html
<label>
  Full Name*
  <input type="text" name="name" placeholder="Your name" required>
</label>
```

Styles:
- Focus: Cyan border + tint + glow
- Valid: Remains default
- Invalid: Error styling (red border)

### Question Options
```html
<label class="option">
  <input type="radio" name="q1" value="Option A">
  <span>Option A text</span>
</label>
```

Behavior:
- Hover: Blue tint + slide right
- Selected: Cyan accent on radio
- Focus: Cyan outline

### Timer Display
```html
<div id="timer" class="timer">
  ⏱ Time left: <span id="timeDisplay">30s</span>
</div>
```

States:
- Normal: Orange pulse animation
- Critical (≤5s): Red with glow animation

## 🏗️ File Structure

```
static/
  └── style.css              # Single comprehensive stylesheet
templates/
  ├── login.html             # Registration & login
  ├── verify.html            # Email code verification
  ├── tutorial.html          # Practice questions
  ├── quiz.html              # Main test with timer
  ├── thankyou.html          # Completion screen
  ├── blocked.html           # Anti-cheat violation screen
  └── admin.html             # Admin dashboard
```

## 🎬 Animation Reference

### Entrance Animations
- **fadeInDown**: Headers (0.8s)
  ```css
  @keyframes fadeInDown {
    from { opacity: 0; transform: translateY(-20px); }
    to { opacity: 1; transform: translateY(0); }
  }
  ```
- **fadeInUp**: Content (0.6s)
  ```css
  @keyframes fadeInUp {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
  }
  ```

### Interactive Animations
- **slideIn**: Option hover (4px right)
- **glow**: Critical timer (1s infinite)
- **pulse**: Timer normal state (2s infinite)

### Bounce Effect (Success)
```css
@keyframes bounce {
  0% { transform: scale(0); }
  50% { transform: scale(1.1); }
  100% { transform: scale(1); }
}
```

## 📱 Responsive Breakpoints

```css
/* Desktop (900px+) */
- Full 500px container width
- 3rem top margin
- All effects enabled

/* Tablet (641px - 900px) */
- Adjusted padding
- Reduced font sizes

/* Mobile (≤640px) */
- 100% width with side margins
- Reduced padding
- Larger touch targets (18px min)
- Simplified animations
```

## 🔧 Customization Examples

### Change Primary Color
Edit `:root` variables in `style.css`:
```css
:root {
  --accent-cyan: #00ff00;        /* Your new color */
  --gradient-primary: linear-gradient(135deg, #1f88ff 0%, #00ff00 100%);
}
```

### Add Dark/Light Mode Toggle
```css
body.light-theme {
  --primary-dark: #ffffff;
  --text-primary: #0f1419;
  --accent-cyan: #0066ff;
  /* ... override other colors */
}
```

### Adjust Animation Speed
Change the duration values in keyframes and animation properties:
```css
h1 {
  animation: fadeInDown 0.4s ease-out;  /* Changed from 0.8s */
}
```

### Reduce Motion (Accessibility)
Already included in CSS:
```css
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

## 🎨 Typography Scale

```
h1:    2.5rem   (40px)   Bold
h3:    1.3rem   (20.8px) SemiBold
body:  0.95rem  (15.2px) Regular
small: 0.9rem   (14.4px) Regular
```

Font Stack (in order):
1. `-apple-system` (iOS Safari)
2. `BlinkMacSystemFont` (macOS Chrome)
3. `Segoe UI` (Windows)
4. `Roboto` (Android)
5. `sans-serif` (Fallback)

## 🚀 Performance Tips

### Already Optimized
✓ CSS-only animations (no JavaScript animation libraries)
✓ GPU-accelerated transforms (translate, scale)
✓ Minimal paint operations
✓ No layout thrashing
✓ 60fps smooth scrolling

### Further Optimization (Optional)
- Inline critical CSS above the fold
- Lazy-load non-critical assets
- Cache static files with service workers
- Use CSS-in-JS only if necessary

## ♿ Accessibility Features

### WCAG AA Compliance
- **Contrast Ratios**: All text ≥4.5:1 (normal) or ≥3:1 (large)
- **Focus States**: Visible outline on all interactive elements
- **Keyboard Navigation**: Tab through all elements
- **Labels**: All form inputs have associated labels
- **Semantic HTML**: Proper heading hierarchy, form structure

### Testing
```html
<!-- Test keyboard navigation -->
Tab through all pages - should see focus indicators
Shift+Tab - should reverse navigation
Enter - should activate buttons/links

<!-- Test screen readers -->
Forms should announce label > input
Errors should be announced
Status updates (timer) should be announced
```

### Screen Reader Support
```html
<div id="timer" aria-live="polite" aria-atomic="true">
  Time left: <span id="timeDisplay">30s</span>
</div>
```

## 🐛 Browser Support

### Officially Supported
- Chrome/Edge: Latest 2 versions
- Firefox: Latest 2 versions
- Safari: Latest 2 versions
- Mobile: iOS Safari 12+, Chrome Android 90+

### Features Used
- CSS Grid (not supported in IE11)
- CSS Custom Properties (not supported in IE11)
- Backdrop Filter (not supported in Firefox yet)
- Linear Gradients (widely supported)

## 📚 Useful CSS Classes

```html
<!-- Containers & Layout -->
<main class="container">           <!-- Centered card -->
<div class="hidden">              <!-- Display: none -->

<!-- Typography -->
<p class="muted">                 <!-- Secondary text color -->
<p class="instructions">          <!-- Highlighted instructions -->

<!-- Forms -->
<label class="consent">           <!-- Checkbox with icon -->
<fieldset>                        <!-- Form group -->

<!-- Components -->
<div class="controls">            <!-- Button group -->
<div class="timer critical">      <!-- Timer in critical state -->
<section class="question hidden"> <!-- Question section -->
```

## 🔐 Anti-Cheat Visual Indicators

The design includes clear visual feedback for security events:

```javascript
// Warning state (yellow/orange)
#timer { color: #ffb74d; }

// Critical state (red with glow)
#timer.critical { 
  color: #ff5252;
  animation: glow 1s infinite;
}

// Violation count
<span id="warnCount">0</span> / {{ max_tab_leaves }}
```

## 📋 Quick Reference Checklist

When making design changes:
- [ ] Test on mobile (320px width)
- [ ] Test on tablet (640px width)
- [ ] Test on desktop (1920px width)
- [ ] Test keyboard navigation
- [ ] Test with screen reader
- [ ] Check color contrast ratios
- [ ] Verify animations don't break with prefers-reduced-motion
- [ ] Check loading performance
- [ ] Test all browser targets

## 🎓 Learning Resources

### CSS Topics Used
- CSS Custom Properties (Variables)
- CSS Grid Layout
- Flexbox
- CSS Gradients
- CSS Animations & Transitions
- CSS Media Queries
- CSS Pseudo-elements (::before, ::after)
- Backdrop Filter

### References
- MDN Web Docs: https://developer.mozilla.org/
- CSS-Tricks: https://css-tricks.com/
- Web.dev: https://web.dev/
- WCAG Guidelines: https://www.w3.org/WAI/WCAG21/quickref/

## 💡 Future Enhancement Ideas

1. **Dark/Light Theme Toggle** - Add theme switcher button
2. **Custom Branding** - Config-based color overrides
3. **Animation Intensity Slider** - Reduce animations for performance
4. **High Contrast Mode** - Increased contrast color scheme
5. **RTL Support** - Right-to-left language support
6. **Sound Effects** - Optional audio feedback
7. **Progress Visualization** - Visual progress bar
8. **Keyboard Shortcuts** - Power-user features

---

**Last Updated**: December 2, 2025  
**Version**: 2.0 - Modern Gaming Professional Design
