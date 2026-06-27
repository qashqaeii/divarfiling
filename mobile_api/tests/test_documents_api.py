"""تست API مدارک و ارسال فایل به مخاطب."""
import io

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from workspace.models import Customer, CustomerActivity, CustomerDocument, CustomerListing

User = get_user_model()


class DocumentsApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09125556666', password='test')
        self.client = APIClient()
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        self.customer = Customer.objects.create(
            user=self.user,
            name='مشتری مدارک',
            phone='09125556666',
            status='جدید',
        )

    def test_upload_and_list_documents(self):
        file = SimpleUploadedFile('contract.pdf', b'pdf-content', content_type='application/pdf')
        resp = self.client.post(
            f'/api/mobile/v1/crm/contacts/{self.customer.pk}/documents',
            {'title': 'قرارداد', 'file': file},
            format='multipart',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.json()['ok'])
        self.assertEqual(CustomerDocument.objects.filter(customer=self.customer).count(), 1)

        list_resp = self.client.get(f'/api/mobile/v1/crm/contacts/{self.customer.pk}/documents')
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(len(list_resp.json()['data']), 1)

    def test_delete_document(self):
        doc = CustomerDocument.objects.create(
            user=self.user,
            customer=self.customer,
            title='مدرک',
            file=SimpleUploadedFile('x.txt', b'x'),
        )
        resp = self.client.delete(
            f'/api/mobile/v1/crm/contacts/{self.customer.pk}/documents/{doc.pk}',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(CustomerDocument.objects.filter(pk=doc.pk).exists())

    def test_send_listing_creates_link_and_activity(self):
        resp = self.client.post(
            f'/api/mobile/v1/crm/contacts/{self.customer.pk}/send-listing',
            {
                'token': 'abc123',
                'title': 'آپارتمان تست',
                'link': 'https://divar.ir/v/abc123',
                'note': 'پیشنهاد ویژه',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.json()['ok'])
        self.assertEqual(CustomerListing.objects.filter(customer=self.customer).count(), 1)
        self.assertTrue(
            CustomerActivity.objects.filter(
                customer=self.customer,
                title='فایل ارسال‌شده به مخاطب',
            ).exists(),
        )

    def test_contact_detail_includes_documents(self):
        CustomerDocument.objects.create(
            user=self.user,
            customer=self.customer,
            title='شناسنامه',
            file=SimpleUploadedFile('id.jpg', b'img'),
        )
        resp = self.client.get(f'/api/mobile/v1/crm/contacts/{self.customer.pk}')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertIn('documents', data)
        self.assertEqual(len(data['documents']), 1)
