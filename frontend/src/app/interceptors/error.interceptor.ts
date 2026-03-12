import { Injectable } from '@angular/core';
import { HttpRequest, HttpHandler, HttpEvent, HttpInterceptor, HttpErrorResponse } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { Router } from '@angular/router';

@Injectable()
export class ErrorInterceptor implements HttpInterceptor {
  constructor(private router: Router) {}

  intercept(request: HttpRequest<any>, next: HttpHandler): Observable<HttpEvent<any>> {
    return next.handle(request).pipe(
      catchError((error: HttpErrorResponse) => {
        let errorMessage = 'An error occurred';
        
        if (error.error instanceof ErrorEvent) {
          // Client-side error
          errorMessage = error.error.message;
        } else {
          // Server-side error
          errorMessage = error.error?.detail || error.statusText;
          
          switch (error.status) {
            case 400:
              errorMessage = error.error?.detail || 'Bad Request';
              break;
            case 401:
              errorMessage = 'Unauthorized - Please login again';
              this.router.navigate(['/login']);
              break;
            case 403:
              errorMessage = 'Forbidden - You do not have permission';
              this.router.navigate(['/unauthorized']);
              break;
            case 404:
              errorMessage = 'Resource not found';
              break;
            case 500:
              errorMessage = 'Internal Server Error';
              break;
          }
        }
        
        console.error(`HTTP Error: ${error.status} - ${errorMessage}`);
        return throwError(() => new Error(errorMessage));
      })
    );
  }
}
