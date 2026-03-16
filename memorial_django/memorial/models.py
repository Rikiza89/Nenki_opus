from django.db import models


class Person(models.Model):
    name = models.CharField(max_length=200, db_index=True)
    death_date = models.CharField(max_length=20, db_index=True)  # ISO: YYYY-MM-DD
    source_file = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.death_date})"

    def get_attributes(self):
        return {a.column_name: a.value for a in self.attributes.all()}


class Attribute(models.Model):
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='attributes')
    column_name = models.CharField(max_length=200)
    value = models.TextField(blank=True)

    class Meta:
        indexes = [models.Index(fields=['person', 'column_name'])]
