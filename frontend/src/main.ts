import { platformBrowserDynamic } from '@angular/platform-browser-dynamic';
import { AppModule } from './app/app.module';

platformBrowserDynamic().bootstrapModule(AppModule)
  .then(() => {
    // Remove loading screen after Angular app has bootstrapped
    const loader = document.getElementById('app-loading');
    if (loader) {
      loader.remove(); // or use loader.style.display = 'none';
    }
  })
  .catch(err => {
    console.error('Angular bootstrap error:', err);
    // Optionally show error message instead of loading screen
    const loader = document.getElementById('app-loading');
    if (loader) {
      loader.innerHTML = '<p style="color: white;">Application failed to load. Please refresh the page.</p>';
    }
  });