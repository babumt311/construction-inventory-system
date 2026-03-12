import { Component } from '@angular/core';
import { Location } from '@angular/common';

@Component({
  selector: 'app-not-found',
  templateUrl: './not-found.component.html',
  styleUrls: ['./not-found.component.scss']
})
export class NotFoundComponent {

  errorCode = 404;
  errorMessage = 'Page Not Found';
  suggestion =
    'The page you are looking for might have been removed, had its name changed, or is temporarily unavailable.';

  constructor(private location: Location) {}

  goBack(): void {
    this.location.back();
  }
}
